"""Real test — Sherlock + WhatsMyName plugin-lərini birlikdə sınayır."""
import asyncio
import time
from src.core.plugin_manager import PluginManager
from src.core.models import Target, TargetType


async def main():
    manager = PluginManager()
    loaded = manager.discover_plugins()
    print(f"Loaded {loaded} plugins:")
    for name, meta in manager.all_plugins.items():
        status = "ON" if manager.is_enabled(name) else "OFF"
        print(f"  [{status}] {meta.name:20s} ({meta.category.value}, {meta.execution_mode.value})")

    print("\n" + "=" * 60)
    target = Target(value="torvalds", type=TargetType.USERNAME)
    print(f"Scanning: {target.value} ({target.type.value})")
    print("=" * 60)

    start = time.monotonic()
    result = await manager.execute_scan([target])
    elapsed = round(time.monotonic() - start, 1)

    print(f"\nResults: {result.findings_count} findings in {elapsed}s")
    print(f"Plugins used: {', '.join(result.plugins_executed)}")
    print(f"Status: {result.status.value}")

    if result.errors:
        print(f"Errors: {result.errors}")

    # Platforma əsasında qruplaşdır
    platforms = {}
    for f in result.findings:
        key = f.raw_data.get("site_name", f.platform)
        if key not in platforms:
            platforms[key] = f

    print(f"\nUnique platforms: {len(platforms)}")
    for name, f in sorted(platforms.items()):
        src = f.raw_data.get("source", f.source_plugin)
        print(f"  {name:25s} [{src:12s}] {f.value}")


if __name__ == "__main__":
    asyncio.run(main())
