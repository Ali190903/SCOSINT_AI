"""Real integration test — bütün plugin-ləri real data ilə sınayır."""
import asyncio
import time
from src.core.plugin_manager import PluginManager
from src.core.models import Target, TargetType


async def scan(manager, value, target_type):
    target = Target(value=value, type=target_type)
    print(f"\n{'='*60}")
    print(f"SCAN: {value} ({target_type.value})")
    print(f"{'='*60}")

    start = time.monotonic()
    result = await manager.execute_scan([target])
    elapsed = round(time.monotonic() - start, 1)

    print(f"Results: {result.findings_count} findings in {elapsed}s")
    print(f"Plugins: {', '.join(result.plugins_executed)}")

    platforms = {}
    for f in result.findings:
        key = f.raw_data.get("site_name", f.platform)
        if key not in platforms:
            platforms[key] = f

    print(f"Unique: {len(platforms)}")
    for name, f in sorted(platforms.items())[:20]:
        print(f"  {name:25s} {f.finding_type.value:15s} {f.value[:60]}")
    if len(platforms) > 20:
        print(f"  ... and {len(platforms)-20} more")
    return result


async def main():
    manager = PluginManager()
    loaded = manager.discover_plugins()
    print(f"Loaded {loaded} plugins:")
    for name, meta in manager.all_plugins.items():
        status = "ON" if manager.is_enabled(name) else "OFF"
        print(f"  [{status}] {meta.name:20s} {meta.category.value:10s} {meta.execution_mode.value}")

    # Test 1: Username scan
    await scan(manager, "torvalds", TargetType.USERNAME)

    # Test 2: Email scan
    await scan(manager, "torvalds@linux-foundation.org", TargetType.EMAIL)


if __name__ == "__main__":
    asyncio.run(main())
