"""Real test — WhatsMyName plugin-i 'torvalds' username-i ilə sınayır."""
import asyncio
from src.plugins.username.whatsmyname_plugin import WhatsMyNamePlugin
from src.core.models import Target, TargetType


async def main():
    plugin = WhatsMyNamePlugin()
    target = Target(value="torvalds", type=TargetType.USERNAME)

    print(f"Scanning username: {target.value}")
    print(f"Plugin: {plugin.meta.name} v{plugin.meta.version}")
    print("-" * 60)

    results = await plugin.execute(target)

    print(f"\nFOUND {len(results)} profiles:\n")
    for f in sorted(results, key=lambda x: x.confidence, reverse=True):
        site = f.raw_data.get("site_name", "?")
        cat = f.raw_data.get("category", "?")
        print(f"  [{cat:10s}] {site:25s} {f.value}")


if __name__ == "__main__":
    asyncio.run(main())
