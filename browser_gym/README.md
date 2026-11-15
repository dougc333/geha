LLM controlling browser

Run `agent.py` from the project environment. Each run writes a JSONL trajectory
to `browser_gym/trajectories/<run-id>.jsonl` and prints the path at startup.
The file contains a start record, one record per browser step, and an end or
error record. Step records include the text observation, model prompt and output,
action, reward, termination flags, environment info, and next text observation. Records are flushed
after every step, so a partial run remains inspectable.

Trajectories can contain page text and chat messages. They stay on this machine
and are excluded from Git.


