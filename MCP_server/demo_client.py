"""Connect to the real stdio server; optionally run the entire simulation."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main(run_all):
    params = StdioServerParameters(command=sys.executable,
                                  args=[str(Path(__file__).with_name('server.py'))])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print('Tools:', ', '.join(t.name for t in (await session.list_tools()).tools))
            response = await session.call_tool('run_all_flows' if run_all else 'list_flows', {})
            if response.isError:
                raise RuntimeError(str(response.content))
            print(json.dumps(response.structuredContent, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-all', action='store_true', help='Create one isolated run of all nine flows')
    asyncio.run(main(parser.parse_args().run_all))
