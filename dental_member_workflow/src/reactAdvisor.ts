import { tool } from "@langchain/core/tools";
import { SystemMessage } from "@langchain/core/messages";
import {
  MessagesAnnotation,
  StateGraph,
  START,
} from "@langchain/langgraph";
import {
  ToolNode,
  toolsCondition,
} from "@langchain/langgraph/prebuilt";
import { ChatOpenAI } from "@langchain/openai";
import { z } from "zod";
import 'dotenv/config';

// Replace these example implementations with your table-RAG,
// provider-directory, and premium-calculation services.

const retrieveDentalBenefits = tool(
  async ({ plan, question }) => {
    return JSON.stringify({
      plan,
      question,
      result: "Example retrieved benefit information",
      citation:
        "2026-geha-dental-plan-brochure.pdf, Benefits section",
    });
  },
  {
    name: "retrieve_dental_benefits",
    description:
      "Retrieve cited benefits from the official GEHA dental documents.",
    schema: z.object({
      plan: z.enum(["High", "Standard"]),
      question: z.string(),
    }),
  },
);

const calculatePremium = tool(
  async ({ plan, enrollmentType, ratingArea }) => {
    // Production code should query an authoritative rate table.
    const exampleMonthlyPremium =
      plan === "High" ? 72.5 : 41.25;

    return JSON.stringify({
      plan,
      enrollmentType,
      ratingArea,
      monthlyPremium: exampleMonthlyPremium,
      currency: "USD",
      source: "2026 GEHA FEDVIP dental rate table",
    });
  },
  {
    name: "calculate_dental_premium",
    description:
      "Calculate a dental premium from the verified rate table.",
    schema: z.object({
      plan: z.enum(["High", "Standard"]),
      enrollmentType: z.enum([
        "Self Only",
        "Self Plus One",
        "Self and Family",
      ]),
      ratingArea: z.string(),
    }),
  },
);

const findNetworkDentist = tool(
  async ({ zipCode }) => {
    return JSON.stringify({
      zipCode,
      providers: [
        {
          name: "Example Dental Provider",
          networkStatus: "in-network",
        },
      ],
    });
  },
  {
    name: "find_network_dentist",
    description: "Find in-network dentists near a ZIP code.",
    schema: z.object({
      zipCode: z.string().regex(/^\d{5}$/),
    }),
  },
);

const tools = [
  retrieveDentalBenefits,
  calculatePremium,
  findNetworkDentist,
];

const apiKey = process.env.OPENAI_API_KEY;
console.log(apiKey)
if (!apiKey) {
  throw new Error("OPENAI_API_KEY is not configured");
}

const model = new ChatOpenAI({
  model: process.env.OPENAI_MODEL ?? "gpt-3.5-turbo",
  temperature: 0,
}).bindTools(tools);

async function advisorNode(
  state: typeof MessagesAnnotation.State,
) {
  const response = await model.invoke([
    new SystemMessage(`
You are a GEHA dental benefits advisor.

Use tools to obtain benefits, premiums, and network information.
Never invent plan facts or prices.

If required information is missing:
- Ask exactly one concise clarifying question.
- Do not make a recommendation yet.

When enough evidence is available:
- Compare High and Standard plans.
- Explain costs and tradeoffs.
- Include citations returned by the tools.
- Do not enroll the member or make eligibility decisions.
`),
    ...state.messages,
  ]);

  return { messages: [response] };
}

export const dentalAdvisor = new StateGraph(MessagesAnnotation)
  .addNode("advisor", advisorNode)
  .addNode("tools", new ToolNode(tools))
  .addEdge(START, "advisor")
  .addConditionalEdges("advisor", toolsCondition)
  .addEdge("tools", "advisor")
  .compile();

// Example invocation
const result = await dentalAdvisor.invoke(
  {
    messages: [
      {
        role: "user",
        content:
          "Compare the High and Standard dental plans for my family in ZIP 95014.",
      },
    ],
  },
  {
    // Bounds the ReAct loop and protects against repeated tool calls.
    recursionLimit: 10,
  },
);

console.log(result.messages.at(-1)?.content);