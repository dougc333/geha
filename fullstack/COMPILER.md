There is no topdown or bottom up parser. 
Multitarget policy compiler. Input a security policy and it outputs several targets at once
1) start with yaml file. 

control.yaml
     │
     ▼
Parser → Typed IR → Semantic analysis → Capability analysis
                                           │
         ┌─────────────────────────────────┼─────────────────────┐
         ▼                                 ▼                     ▼
   Org Policy emitter               IAM/PAB emitters       VPC-SC/SCC emitters
         │                                 │                     │
         └───────────────────── Artifact bundle ─────────────────┘
                                           │
                                  Simulate → Approve → Apply

1. Begin with YAML, not a custom parser
A custom textual language can come later. YAML plus a strict schema is faster to build and easier to integrate with GitOps.



