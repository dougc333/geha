import { randomUUID } from "node:crypto";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { DescribeTasksCommand, ECSClient, ListTasksCommand } from "@aws-sdk/client-ecs";
import { CloudWatchLogsClient, GetLogEventsCommand } from "@aws-sdk/client-cloudwatch-logs";
import { GetObjectCommand, PutObjectCommand, paginateListObjectsV2, S3Client } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

function awsDocuments(): Plugin {
  return {
    name: "local-aws-documents",
    configureServer(server) {
      const bucket = process.env.AWS_DOCLING_BUCKET;
      const region = process.env.AWS_REGION || process.env.AWS_DEFAULT_REGION;
      const cluster = process.env.AWS_DOCLING_CLUSTER || "aws-docling";
      const s3 = new S3Client({ region });
      const ecs = new ECSClient({ region });
      const logs = new CloudWatchLogsClient({ region });
      server.middlewares.use(async (req, res, next) => {
        if (!req.url?.startsWith("/api/documents") && !req.url?.startsWith("/api/markdown") && !req.url?.startsWith("/api/upload") && !req.url?.startsWith("/api/status")) return next();
        res.setHeader("Cache-Control", "no-store");
        if (!bucket) {
          res.statusCode = 503;
          res.end(JSON.stringify({ error: "Set AWS_DOCLING_BUCKET before starting the viewer." }));
          return;
        }
        try {
          const url = new URL(req.url, "http://localhost");
          if (url.pathname === "/api/documents") {
            const documents = new Map<string, { id: string; name: string; markdownKey?: string; pdfUrl: string; status: string }>();
            for await (const page of paginateListObjectsV2({ client: s3 }, { Bucket: bucket, Prefix: "incoming/" })) {
              for (const object of page.Contents ?? []) {
                const key = object.Key;
                if (!key?.toLowerCase().endsWith(".pdf")) continue;
                const relative = key.slice("incoming/".length, -4);
                documents.set(relative, {
                  id: `aws:${relative}`,
                  name: relative,
                  pdfUrl: await getSignedUrl(s3, new GetObjectCommand({ Bucket: bucket, Key: key }), { expiresIn: 900 }),
                  status: "processing",
                });
              }
            }
            for await (const page of paginateListObjectsV2({ client: s3 }, { Bucket: bucket, Prefix: "extracted/" })) {
              for (const object of page.Contents ?? []) {
                const key = object.Key;
                if (!key?.endsWith(".md")) continue;
                const relative = key.slice("extracted/".length, -3);
                const existing = documents.get(relative);
                if (existing) {
                  existing.markdownKey = key;
                  existing.status = "complete";
                }
              }
            }
            const result = [...documents.values()].sort((a, b) => a.name.localeCompare(b.name));
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify(result));
          } else if (url.pathname === "/api/upload" && req.method === "POST") {
            const name = url.searchParams.get("name") ?? "";
            if (!/^[A-Za-z0-9][A-Za-z0-9._-]*\.pdf$/i.test(name)) {
              res.statusCode = 400;
              res.end(JSON.stringify({ error: "Use a simple PDF filename." }));
              return;
            }
            const chunks: Buffer[] = [];
            let size = 0;
            for await (const chunk of req) {
              const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
              size += bytes.length;
              if (size > 25_000_000) {
                res.statusCode = 413;
                res.end(JSON.stringify({ error: "PDF exceeds 25 MB upload limit." }));
                return;
              }
              chunks.push(bytes);
            }
            const body = Buffer.concat(chunks);
            if (body.length < 5 || body.toString("ascii", 0, 5) !== "%PDF-") {
              res.statusCode = 400;
              res.end(JSON.stringify({ error: "File is not a PDF." }));
              return;
            }
            const storedName = `${randomUUID()}-${name}`;
            await s3.send(new PutObjectCommand({ Bucket: bucket, Key: `incoming/${storedName}`, Body: body, ContentType: "application/pdf" }));
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ name: storedName, status: "processing" }));
          } else if (url.pathname === "/api/status") {
            const name = url.searchParams.get("name") ?? "";
            if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(name)) {
              res.statusCode = 400;
              res.end(JSON.stringify({ error: "Invalid document name" }));
              return;
            }
            let taskArn: string | undefined;
            try {
              const object = await s3.send(new GetObjectCommand({ Bucket: bucket, Key: `jobs/${name}.json` }));
              const job = JSON.parse(await object.Body?.transformToString() ?? "{}");
              taskArn = job.task;
            } catch (error) {
              if ((error as { $metadata?: { httpStatusCode?: number } }).$metadata?.httpStatusCode !== 404) throw error;
            }
            // Existing uploads predate job markers; find their task by its source URL.
            if (!taskArn) {
              for (const desiredStatus of ["RUNNING", "STOPPED"] as const) {
                const listed = await ecs.send(new ListTasksCommand({ cluster, desiredStatus, maxResults: 100 }));
                if (!listed.taskArns?.length) continue;
                const described = await ecs.send(new DescribeTasksCommand({ cluster, tasks: listed.taskArns }));
                const found = described.tasks?.find((task) => {
                  const source = task.overrides?.containerOverrides?.flatMap((item) => item.environment ?? [])
                    .find((item) => item.name === "SOURCE_URL")?.value;
                  if (!source) return false;
                  try { return decodeURIComponent(new URL(source).pathname).endsWith(`/incoming/${name}.pdf`); }
                  catch { return false; }
                });
                if (found?.taskArn) { taskArn = found.taskArn; break; }
              }
            }
            let status = "queued";
            let taskId: string | undefined;
            let messages: Array<{ time: string; message: string }> = [];
            let heartbeatAgeSeconds: number | undefined;
            let detail = "Waiting for the S3 event to start a task.";
            if (taskArn) {
              taskId = taskArn.split("/").pop();
              const described = await ecs.send(new DescribeTasksCommand({ cluster, tasks: [taskArn] }));
              const task = described.tasks?.[0];
              const container = task?.containers?.find((item) => item.name === "docling-worker");
              if (task?.lastStatus === "STOPPED") {
                status = container?.exitCode === 0 ? "complete" : "failed";
                detail = container?.reason || task.stoppedReason || `Container exit code ${container?.exitCode ?? "unknown"}`;
              } else if (task?.lastStatus === "RUNNING") {
                status = "converting";
                detail = "Docling is converting the PDF.";
              } else {
                status = "starting";
                detail = `ECS task ${task?.lastStatus?.toLowerCase() ?? "pending"}; image pull may take time.`;
              }
              try {
                const events = await logs.send(new GetLogEventsCommand({
                  logGroupName: `/ecs/${cluster}`,
                  logStreamName: `worker/docling-worker/${taskId}`,
                  limit: 80,
                  startFromHead: false,
                }));
                messages = (events.events ?? []).map((event) => ({
                  time: event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "",
                  message: event.message ?? "",
                }));
                const heartbeat = [...(events.events ?? [])].reverse().find((event) => event.message?.startsWith("heartbeat "));
                if (heartbeat?.timestamp) heartbeatAgeSeconds = Math.max(0, Math.floor((Date.now() - heartbeat.timestamp) / 1000));
              } catch (error) {
                if ((error as { name?: string }).name !== "ResourceNotFoundException") throw error;
              }
            }
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ status, detail, taskId, heartbeatAgeSeconds, messages }));
          } else if (url.pathname === "/api/markdown") {
            const key = url.searchParams.get("key") ?? "";
            if (!key.startsWith("extracted/") || !key.endsWith(".md") || key.includes("..")) {
              res.statusCode = 400;
              res.end("Invalid Markdown key");
              return;
            }
            const object = await s3.send(new GetObjectCommand({ Bucket: bucket, Key: key }));
            if ((object.ContentLength ?? 0) > 10_000_000) {
              res.statusCode = 413;
              res.end("Markdown exceeds 10 MB viewer limit");
              return;
            }
            res.setHeader("Content-Type", "text/markdown; charset=utf-8");
            res.end(await object.Body?.transformToString() ?? "");
          } else next();
        } catch (error) {
          res.statusCode = 502;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ error: error instanceof Error ? error.message : String(error) }));
        }
      });
    },
  };
}

export default defineConfig({ plugins: [react(), awsDocuments()] });
