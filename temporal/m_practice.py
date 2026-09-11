import sys
import asyncio
from w_practice import GreetSomeone




async def main():
    name = sys.argv[1]
    greeter = GreetSomeone()
    greeting = await greeter.run(name)
    print(greeting)

if __name__=="__main__":
    asyncio.run(main())
  
