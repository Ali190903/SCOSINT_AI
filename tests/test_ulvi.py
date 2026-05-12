"""Real test — 'Ulvi Abdullazade' üçün kombinasiyalar yaradır və yoxlayır."""
import asyncio
from src.plugins.alias.alias_generator_plugin import AliasGeneratorPlugin
from src.plugins.username.whatsmyname_plugin import WhatsMyNamePlugin
from src.plugins.username.maigret_plugin import MaigretPlugin
from src.core.models import Target, TargetType
import sys

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    name = "Ulvi Abdullazade"
    print(f"[*] Hədəf: {name}")
    
    # 1. Alias-ları yaradırıq
    alias_plugin = AliasGeneratorPlugin()
    target_name = Target(value=name, type=TargetType.NAME)
    alias_results = await alias_plugin.execute(target_name)
    
    # Ən əsas username variantlarını (confidence > 0.8) seçirik
    usernames = []
    for finding in sorted(alias_results, key=lambda x: x.confidence, reverse=True):
        usernames.append(finding.value)
    
    # Nümunə üçün ən ehtimallı 3 variantı götürürük
    top_usernames = usernames[:3]
    if "ulviabdullazade" not in top_usernames:
        top_usernames.insert(0, "ulviabdullazade")
        
    print(f"[*] Ən ehtimallı Username-lər: {top_usernames}")
    
    # 2. WhatsMyName ilə axtarırıq (sürətlidir deyə)
    wmn_plugin = WhatsMyNamePlugin()
    maigret_plugin = MaigretPlugin()
    
    for un in top_usernames:
        print(f"\n==========================================")
        print(f"Axtarılır: {un}")
        print(f"==========================================")
        
        target_un = Target(value=un, type=TargetType.USERNAME)
        
        # WMN Axtarışı
        print(">> WhatsMyName axtarır...")
        wmn_results = await wmn_plugin.execute(target_un)
        if wmn_results:
            print(f"   [+] WhatsMyName {len(wmn_results)} profil tapdı:")
            for r in wmn_results[:5]:
                print(f"       - {r.value}")
        else:
            print("   [-] WhatsMyName heç nə tapmadı.")
            
        # Maigret Axtarışı
        print("\n>> Maigret axtarır (10 saniyə limit)...")
        maigret_results = await maigret_plugin.execute(target_un)
        if maigret_results:
            print(f"   [+] Maigret {len(maigret_results)} profil tapdı:")
            for r in maigret_results[:5]:
                print(f"       - {r.value}")
        else:
            print("   [-] Maigret heç nə tapmadı.")

if __name__ == "__main__":
    asyncio.run(main())
