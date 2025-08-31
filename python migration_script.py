#!/usr/bin/env python3
"""
Script de Migration LinkedIn Monitor v3.0 → v4.0 API
Migration automatisée vers l'API officielle LinkedIn
"""
import csv
import re
import os
import shutil
from datetime import datetime
from typing import List, Dict


def extract_profile_id_from_url(url: str) -> str:
    """Extraction automatique de l'ID depuis l'URL LinkedIn"""
    url = url.strip().rstrip('/')
    
    # Company ID
    company_match = re.search(r'/company/([^/]+)', url)
    if company_match:
        return company_match.group(1)
    
    # Personal profile ID
    profile_match = re.search(r'/in/([^/]+)', url)
    if profile_match:
        return profile_match.group(1)
    
    return ""


def detect_profile_type(url: str) -> str:
    """Détection du type de profil"""
    if '/company/' in url:
        return 'company'
    elif '/in/' in url:
        return 'person'
    return 'unknown'


def migrate_csv_to_api_format(input_file: str, output_file: str) -> bool:
    """Migration du CSV vers le format API v4.0"""
    try:
        print(f"🔄 Migration CSV: {input_file} → {output_file}")
        
        # Backup de l'ancien fichier
        if os.path.exists(input_file):
            backup_file = f"{input_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(input_file, backup_file)
            print(f"💾 Backup créé: {backup_file}")
        
        # Lecture ancien format
        profiles = []
        
        with open(input_file, 'r', encoding='utf-8-sig', newline='') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                url = row.get('URL', '').strip()
                name = row.get('Name', '').strip()
                last_post_id = row.get('Last_Post_ID', '').strip()
                error_count = row.get('Error_Count', '0').strip()
                
                if url and name:
                    # Extraction automatique de l'ID
                    profile_id = extract_profile_id_from_url(url)
                    profile_type = detect_profile_type(url)
                    
                    profiles.append({
                        'URL': url,
                        'Name': name,
                        'Profile_ID': profile_id,
                        'Last_Post_ID': last_post_id,
                        'Error_Count': error_count,
                        'Profile_Type': profile_type
                    })
                    
                    print(f"✅ Migré: {name} → ID: {profile_id} ({profile_type})")
        
        # Écriture nouveau format
        fieldnames = ['URL', 'Name', 'Profile_ID', 'Last_Post_ID', 'Error_Count']
        
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            
            for profile in profiles:
                writer.writerow({
                    'URL': profile['URL'],
                    'Name': profile['Name'],
                    'Profile_ID': profile['Profile_ID'],
                    'Last_Post_ID': profile['Last_Post_ID'],
                    'Error_Count': profile['Error_Count']
                })
        
        print(f"🎉 Migration réussie: {len(profiles)} profils migrés")
        
        # Rapport de migration
        companies = len([p for p in profiles if p['Profile_Type'] == 'company'])
        persons = len([p for p in profiles if p['Profile_Type'] == 'person'])
        
        print(f"📊 Répartition:")
        print(f"   🏢 Entreprises: {companies}")
        print(f"   👤 Profils personnels: {persons}")
        
        if persons > 0:
            print(f"⚠️ ATTENTION: {persons} profil(s) personnel(s) détecté(s)")
            print("   Les profils personnels nécessitent des permissions étendues")
            print("   Commencez avec les entreprises pour tester l'API")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur migration: {e}")
        return False


def create_env_template():
    """Création du template .env"""
    env_content = """# LinkedIn Monitor v4.0 - Configuration API
# ==========================================

# Configuration Email
GMAIL_EMAIL=votre_email@gmail.com
GMAIL_APP_PASSWORD=votre_mot_de_passe_application_gmail
RECIPIENT_EMAIL=destinataire@example.com

# Configuration API LinkedIn
# Obtenez ces valeurs sur https://www.linkedin.com/developers/
LINKEDIN_CLIENT_ID=votre_client_id_linkedin
LINKEDIN_CLIENT_SECRET=votre_client_secret_linkedin

# Token d'accès (optionnel - généré automatiquement)
# LINKEDIN_ACCESS_TOKEN=votre_token_si_disponible

# Configuration avancée
DEBUG_MODE=false
MAX_POSTS_PER_PROFILE=10
API_DELAY_SECONDS=20
"""
    
    with open('.env.template', 'w', encoding='utf-8') as file:
        file.write(env_content)
    
    print("✅ Template .env créé: .env.template")


def validate_api_readiness(csv_file: str) -> Dict[str, any]:
    """Validation de la préparation API"""
    print("🔍 Validation de la préparation API...")
    
    report = {
        'csv_ready': False,
        'profiles_count': 0,
        'companies_count': 0,
        'persons_count': 0,
        'missing_ids': [],
        'recommendations': []
    }
    
    try:
        if not os.path.exists(csv_file):
            report['recommendations'].append("❌ Fichier CSV manquant - sera créé automatiquement")
            return report
        
        with open(csv_file, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                url = row.get('URL', '').strip()
                name = row.get('Name', '').strip()
                profile_id = row.get('Profile_ID', '').strip()
                
                if url and name:
                    report['profiles_count'] += 1
                    
                    profile_type = detect_profile_type(url)
                    if profile_type == 'company':
                        report['companies_count'] += 1
                    elif profile_type == 'person':
                        report['persons_count'] += 1
                    
                    if not profile_id:
                        auto_id = extract_profile_id_from_url(url)
                        report['missing_ids'].append({
                            'name': name,
                            'url': url,
                            'suggested_id': auto_id,
                            'type': profile_type
                        })
        
        report['csv_ready'] = len(report['missing_ids']) == 0
        
        # Recommandations
        if report['missing_ids']:
            report['recommendations'].append(f"🔧 {len(report['missing_ids'])} Profile_ID manquant(s) - Migration requise")
        
        if report['persons_count'] > 0:
            report['recommendations'].append(f"⚠️ {report['persons_count']} profil(s) personnel(s) - Permissions étendues requises")
        
        if report['companies_count'] == 0:
            report['recommendations'].append("💡 Ajoutez des Company Pages pour commencer facilement")
        
        return report
        
    except Exception as e:
        print(f"❌ Erreur validation: {e}")
        report['recommendations'].append(f"❌ Erreur lecture CSV: {e}")
        return report


def print_migration_report(report: Dict[str, any]):
    """Affichage du rapport de migration"""
    print("\n" + "🚀" + "=" * 70 + "🚀")
    print("📊 RAPPORT DE PRÉPARATION API v4.0")
    print("🚀" + "=" * 70 + "🚀")
    
    print(f"📈 Profils total: {report['profiles_count']}")
    print(f"🏢 Entreprises: {report['companies_count']}")
    print(f"👤 Profils personnels: {report['persons_count']}")
    print(f"✅ CSV prêt pour API: {'OUI' if report['csv_ready'] else 'NON'}")
    
    if report['missing_ids']:
        print(f"\n🔧 PROFILE_ID MANQUANTS ({len(report['missing_ids'])}):")
        for missing in report['missing_ids']:
            print(f"   • {missing['name']} ({missing['type']})")
            print(f"     URL: {missing['url']}")
            print(f"     ID suggéré: {missing['suggested_id']}")
            print()
    
    if report['recommendations']:
        print("💡 RECOMMANDATIONS:")
        for rec in report['recommendations']:
            print(f"   {rec}")
    
    print("\n🎯 PROCHAINES ÉTAPES:")
    if not report['csv_ready']:
        print("   1. 🔄 Exécuter la migration automatique du CSV")
    print("   2. 🔐 Configurer les secrets API LinkedIn sur GitHub")
    print("   3. 🚀 Déployer le workflow v4.0")
    print("   4. 🎨 Profiter des emails ultra-premium avec contenu authentique!")
    
    print("🚀" + "=" * 70 + "🚀")


def main():
    """Migration principale"""
    print("🚀" + "=" * 80 + "🚀")
    print("🔥 MIGRATION LINKEDIN MONITOR v3.0 → v4.0 API OFFICIELLE")
    print("🚀" + "=" * 80 + "🚀")
    
    csv_file = "linkedin_urls.csv"
    
    try:
        # 1. Validation actuelle
        print("🔍 ÉTAPE 1: Validation de l'état actuel")
        report = validate_api_readiness(csv_file)
        print_migration_report(report)
        
        # 2. Migration si nécessaire
        if not report['csv_ready'] and os.path.exists(csv_file):
            print(f"\n🔄 ÉTAPE 2: Migration automatique du CSV")
            
            response = input("Voulez-vous migrer automatiquement le CSV? (y/N): ").strip().lower()
            if response in ['y', 'yes', 'oui']:
                backup_file = f"{csv_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                success = migrate_csv_to_api_format(csv_file, csv_file)
                
                if success:
                    print("🎉 Migration CSV réussie!")
                else:
                    print("❌ Échec migration CSV")
            else:
                print("⏭️ Migration manuelle requise")
        
        # 3. Création template
        print(f"\n📝 ÉTAPE 3: Création du template de configuration")
        create_env_template()
        
        # 4. Instructions finales
        print(f"\n🎯 ÉTAPE 4: Instructions finales")
        print("✅ Migration préparée avec succès!")
        print("\n📋 ACTIONS REQUISES:")
        print("   1. 🔐 Créer une app LinkedIn sur https://www.linkedin.com/developers/")
        print("   2. 🔑 Configurer les secrets GitHub avec vos credentials API")
        print("   3. 🚀 Déployer le nouveau workflow GitHub Actions")
        print("   4. 🎨 Tester avec un profil d'entreprise")
        
        print(f"\n🔥 AVANTAGES v4.0 API:")
        print("   • 🎯 Extraction authentique des vrais titres/descriptions")
        print("   • 💬 Données d'engagement temps réel")
        print("   • 🛡️ Stabilité maximale et conformité LinkedIn")
        print("   • 🎨 Emails ultra-premium avec contenu véritable")
        print("   • ⚡ Performance optimisée et gestion des quotas")
        
        print("\n🚀 Prêt pour la révolution API LinkedIn ! 🚀")
        
    except Exception as e:
        print(f"💥 Erreur migration: {e}")
        return False
    
    return True


if __name__ == "__main__":
    main()
