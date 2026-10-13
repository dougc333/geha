Over 50% of the RAG POCs fail. Why?

1) Chunking destroys document structure. At scale it is impossible to tell which chunks are relevant. Relevant !== Vector Similarity. 
2) Reranking doesnt work at scale. More than 6 chunks the LLM loses ability with a shrinking context window. 
3) Multihop doesn't work at scale. Agentic multihop works great in small scale but fails when there are errors in the earlier hops. Impossible to recover. 
4) RAG primary goal is to reduce hallucinations which isn't in universal agreement as to the benefit of RAG. Intrinsic rates min are 7%. The reason most people build RAG is for access to internal docs. 7% means can't measure in POC but will see nonrepeatable failures in production. A chatbot telling someone isn't covered when they are makes people really mad. Hard to recover from. 
5) Can't debug LLMs. Not repeatable and if it were how do you fix it? 

Most of the lessons from keyword search from 15y ago old. Most search engine POCs failed. 

Lessons: return tables and figures if possible. those have natural structure. Return a db query, construct a hierarchial RAG system. Never mix postal worker benefit polcies  docs into same vector db as non postal workers. Not worth it. Rookie Misake. Impossible to debug and fix later. Great for cherry picked query demos. 
Lessons: small RAG indexes. Less than 6 ranked results sent to LLM before creating user response. Make it a tool call. Let the agent decide which RAG system it wants. 
Lessons: Always assign some structure to a document or chunks. Do not return chunks to the user if at possible
Lessons: Reduce cost of Anthropic and OpenAI for experimentation and getting to gold use cases before mgmt loses patience and overrunning budget. 
Lessons: never do a POC on the strongest model. Use the weakest, try to design LLM calls in self correcting loop. If no loop your sw will fail. 

