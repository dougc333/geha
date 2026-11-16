import { randomUUID } from "node:crypto";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { GetObjectCommand, PutObjectCommand, paginateListObjectsV2, S3Client } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

function awsDocuments(): Plugin {
  return {
    name: "local-aws-documents",
    configureServer(server) {
      const bucket = process.env.AWS_DOCLING_BUCKET;
      const s3 = new S3Client({ region: process.env.AWS_REGION || process.env.AWS_DEFAULT_REGION });
      server.middlewares.use(async (req, res, next) => {
        if (!req.url?.startsWith("/api/documents") && !req.url?.startsWith("/api/markdown") && !req.url?.startsWith("/api/upload")) return next();
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
