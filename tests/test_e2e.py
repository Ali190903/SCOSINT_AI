"""Tam E2E (End-to-End) Döyüş Testi."""
import asyncio
import sys

from src.core.models import Target, TargetType
from src.plugins.alias.alias_generator_plugin import AliasGeneratorPlugin
from src.plugins.breach.hibp_plugin import HIBPPlugin
from src.plugins.email.holehe_plugin import HolehePlugin
from src.plugins.email.gravatar_plugin import GravatarPlugin
from src.plugins.username.whatsmyname_plugin import WhatsMyNamePlugin
from src.plugins.username.sherlock_plugin import SherlockPlugin
from src.plugins.username.maigret_plugin import MaigretPlugin

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    email_str = "alonewithpc@gmail.com"
    name_str = "Əli Aslanzadə"
    
    print("="*60)
    print(" 🚀 SCOSINT_AI TAM E2E TEST BAŞLAYIR")
    print("="*60)
    
    # 1. EMAIL AXTARIŞI
    print(f"\n[EMAIL AXTARIŞI] -> {email_str}")
    target_email = Target(value=email_str, type=TargetType.EMAIL)
    
    hibp = HIBPPlugin()
    print(">> LeakCheck (Sızma) yoxlanılır...")
    leak_results = await hibp.execute(target_email)
    if leak_results:
        print(f"   [+] Sızmalar tapıldı ({len(leak_results)}):")
        for r in leak_results[:5]:
            print(f"       - {r.value}")
    else:
        print("   [-] Heç bir sızma tapılmadı.")
        
    gravatar = GravatarPlugin()
    print("\n>> Gravatar (Profil şəkli və məlumat) yoxlanılır...")
    gravatar_results = await gravatar.execute(target_email)
    if gravatar_results:
        print(f"   [+] Gravatar məlumatı tapıldı:")
        for r in gravatar_results:
            print(f"       - {r.value}")
    else:
        print("   [-] Gravatar tapılmadı.")
        
    holehe = HolehePlugin()
    print("\n>> Holehe (Qeydiyyatdan keçilmiş saytlar) yoxlanılır (15-20 san)...")
    holehe_results = await holehe.execute(target_email)
    if holehe_results:
        print(f"   [+] Holehe {len(holehe_results)} saytda hesab tapdı:")
        for r in holehe_results[:10]:
            print(f"       - {r.value}")
    else:
        print("   [-] Holehe heç nə tapmadı.")

    # 2. AD/USERNAME AXTARIŞI
    print(f"\n[AD/USERNAME AXTARIŞI] -> {name_str}")
    target_name = Target(value=name_str, type=TargetType.NAME)
    
    alias_plugin = AliasGeneratorPlugin()
    print(">> AliasGenerator ilə ad kombinasiyaları yaradılır...")
    aliases = await alias_plugin.execute(target_name)
    top_aliases = [f.value for f in sorted(aliases, key=lambda x: x.confidence, reverse=True)[:3]]
    print(f"   [+] Ən ehtimallı istifadəçi adları: {top_aliases}")
    
    wmn = WhatsMyNamePlugin()
    sherlock = SherlockPlugin()
    maigret = MaigretPlugin()
    
    for un in top_aliases:
        print(f"\n==========================================")
        print(f"Axtarılır: {un}")
        print(f"==========================================")
        target_un = Target(value=un, type=TargetType.USERNAME)
        
        print(">> WhatsMyName...")
        res = await wmn.execute(target_un)
        print(f"   Tapıldı: {len(res)} profil")
        
        print(">> Sherlock (yeni CSV mexanizmi ilə)...")
        res = await sherlock.execute(target_un)
        print(f"   Tapıldı: {len(res)} profil")
        
        print(">> Maigret (yeni JSON mexanizmi ilə)...")
        res = await maigret.execute(target_un)
        print(f"   Tapıldı: {len(res)} profil")

if __name__ == "__main__":
    asyncio.run(main())
