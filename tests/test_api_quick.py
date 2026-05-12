"""Alias generator test."""
import asyncio
from src.plugins.alias.alias_generator_plugin import AliasGeneratorPlugin
from src.core.models import Target, TargetType


async def main():
    plugin = AliasGeneratorPlugin()

    names = ["Muhammad Ali", "Hüseyn Əliyev", "Владимир Путин", "John Smith"]
    for name in names:
        target = Target(value=name, type=TargetType.NAME)
        results = await plugin.execute(target)
        print(f"\n{name} -> {len(results)} aliases:")
        for f in results[:15]:
            print(f"  {f.value}")
        if len(results) > 15:
            print(f"  ... +{len(results)-15} more")


if __name__ == "__main__":
    asyncio.run(main())
