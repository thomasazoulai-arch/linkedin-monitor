#!/usr/bin/env python3
import requests
import csv
import time
from datetime import datetime
import os
import re
import hashlib
import smtplib
import sys
import traceback

class LinkedInMonitor:
    def __init__(self, csv_file_path, email_config):
        self.csv_file_path = csv_file_path
        self.email_config = email_config
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        print(f"✅ LinkedInMonitor initialisé")
    
    def create_default_csv(self):
        """Crée un fichier CSV par défaut s'il n'existe pas"""
        try:
            print("📝 Création d'un fichier CSV par défaut")
            
            default_data = [
                {
                    'URL': 'https://www.linkedin.com/company/microsoft/',
                    'Name': 'Microsoft',
                    'Last_Post_ID': ''
                },
                {
                    'URL': 'https://www.linkedin.com/company/tesla-motors/',
                    'Name': 'Tesla',
                    'Last_Post_ID': ''
                }
            ]
            
            fieldnames = ['URL', 'Name', 'Last_Post_ID']
            
            with open(self.csv_file_path, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(default_data)
            
            print("✅ Fichier CSV créé avec les données par défaut")
            return default_data
            
        except Exception as e:
            print(f"❌ Erreur création CSV: {e}")
            return None

    def load_urls_from_csv(self):
        """Charge les URLs depuis le fichier CSV"""
        try:
            print(f"📁 Chargement du fichier: {self.csv_file_path}")
            
            if not os.path.exists(self.csv_file_path):
                print(f"❌ Fichier {self.csv_file_path} introuvable")
                print("📂 Création d'un fichier par défaut...")
                return self.create_default_csv()
            
            data = []
            
            # Essaie plusieurs encodages
            encodings = ['utf-8', 'utf-8-sig', 'iso-8859-1', 'cp1252', 'latin1']
            
            for encoding in encodings:
                try:
                    print(f"🔄 Tentative avec encodage: {encoding}")
                    with open(self.csv_file_path, 'r', encoding=encoding, newline='') as file:
                        reader = csv.DictReader(file)
                        for row in reader:
                            data.append(row)
                    print(f"✅ Succès avec {encoding} - {len(data)} lignes chargées")
                    break
                except UnicodeDecodeError:
                    print(f"❌ Échec avec {encoding}")
                    data = []
                    continue
            
            if not data:
                print("❌ Impossible de lire le fichier avec tous les encodages testés")
                print("📂 Création d'un fichier par défaut...")
                return self.create_default_csv()
            
            # Ajouter Last_Post_ID si manquant
            for row in data:
                if 'Last_Post_ID' not in row:
                    row['Last_Post_ID'] = ''
            
            return data
            
        except Exception as e:
            print(f"❌ Erreur chargement: {e}")
            traceback.print_exc()
            return None
    
    def save_urls_to_csv(self, data):
        """Sauvegarde le fichier CSV"""
        try:
            print("💾 Sauvegarde...")
            
            if not data:
                return False
            
            fieldnames = list(data[0].keys())
            
            # Sauvegarde avec encodage UTF-8 et BOM pour compatibilité
            with open(self.csv_file_path, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            
            print("✅ Fichier sauvegardé en UTF-8")
            return True
            
        except Exception as e:
            print(f"❌ Erreur sauvegarde: {e}")
            return False
    
    def extract_linkedin_info(self, html_content):
        """Extrait des informations du contenu HTML LinkedIn"""
        try:
            info = {
                'activity_found': False,
                'content_hash': '',
                'activity_count': 0
            }
            
            # Patterns LinkedIn typiques
            activity_patterns = [
                r'(\d+)\s*(likes?|comments?|reactions?)',
                r'posted this',
                r'shared this',
                r'commented on this',
                r'activity-\w+',
                r'feed-shared-update'
            ]
            
            activity_count = 0
            for pattern in activity_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    activity_count += len(matches)
                    info['activity_found'] = True
            
            info['activity_count'] = activity_count
            
            # Hash du contenu pour détecter les changements
            content_sample = html_content[:8000]  # Plus de contenu
            info['content_hash'] = hashlib.sha256(content_sample.encode('utf-8', errors='ignore')).hexdigest()[:16]
            
            return info
            
        except Exception as e:
            print(f"❌ Erreur extraction: {e}")
            return {'activity_found': False, 'content_hash': 'error', 'activity_count': 0}
    
    def check_linkedin_page(self, url, name):
        """Vérification d'une page LinkedIn"""
        try:
            print(f"🌐 Vérification de {name}...")
            
            # Pause pour éviter les limitations
            time.sleep(6)
            
            # Préparation URL pour les pages company
            check_url = url
            if 'company' in url and 'posts' not in url and not url.endswith('/posts/'):
                if not url.endswith('/'):
                    check_url += '/'
                check_url += 'posts/'
                print(f"🔄 URL modifiée pour posts: {check_url}")
            
            response = requests.get(check_url, headers=self.headers, timeout=25)
            
            if response.status_code == 200:
                print(f"✅ Page accessible ({len(response.text)} caractères)")
                
                # Extraction des infos
                info = self.extract_linkedin_info(response.text)
                
                result = {
                    'id': info['content_hash'],
                    'name': name,
                    'url': check_url,
                    'original_url': url,
                    'timestamp': datetime.now().isoformat(),
                    'activity_found': info['activity_found'],
                    'activity_count': info['activity_count'],
                    'status': 'success'
                }
                
                print(f"✅ ID généré: {result['id']}")
                print(f"📊 Activités trouvées: {info['activity_count']}")
                
                return result
                
            elif response.status_code == 999:
                print(f"⚠️ Limite LinkedIn (999) - tentative avec URL originale")
                # Essai avec URL originale
                if check_url != url:
                    time.sleep(10)
                    return self.check_linkedin_page(url, name + " (fallback)")
                else:
                    print(f"❌ Bloqué par LinkedIn")
                    return None
            else:
                print(f"❌ HTTP {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Erreur vérification: {e}")
            return None
    
    def send_simple_email(self, post_info):
        """Envoi d'email ultra-simple sans modules complexes"""
        try:
            print(f"📧 Envoi notification pour {post_info['name']}...")
            
            sender_email = self.email_config['sender_email']
            sender_password = self.email_config['sender_password']
            recipient_email = self.email_config['recipient_email']
            
            # Formatage de la date
            try:
                timestamp_obj = datetime.fromisoformat(post_info['timestamp'])
                date_str = timestamp_obj.strftime('%d/%m/%Y à %H:%M')
            except:
                date_str = str(post_info['timestamp'])
            
            # Construction du message email simple
            subject = f"LinkedIn Alert - {post_info['name']}"
            
            body = f"""Nouvelle activite LinkedIn detectee !

Profil/Entreprise: {post_info['name']}
URL: {post_info['url']}
Date detection: {date_str}
ID suivi: {post_info['id']}
Activites trouvees: {post_info['activity_count']}

---
Agent LinkedIn automatise
Surveille vos pages LinkedIn 24h/24
"""
            
            # Message email simple au format RFC
            email_message = f"""From: {sender_email}
To: {recipient_email}
Subject: {subject}
Content-Type: text/plain; charset=utf-8

{body}"""
            
            # Envoi SMTP direct
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, [recipient_email], email_message.encode('utf-8'))
            
            print("✅ Email envoyé avec succès")
            return True
            
        except Exception as e:
            print(f"❌ Erreur email: {e}")
            traceback.print_exc()
            return False
    
    def run_monitoring(self):
        """Processus principal de monitoring"""
        try:
            print("=" * 60)
            print(f"🚀 DÉBUT MONITORING - {datetime.now()}")
            print("=" * 60)
            
            # Chargement des données
            data = self.load_urls_from_csv()
            if not data:
                print("❌ Impossible de charger les données")
                return False
            
            total_profiles = len(data)
            successful_checks = 0
            changes_detected = 0
            changes_made = False
            
            print(f"📋 {total_profiles} profils à vérifier")
            
            for i, row in enumerate(data):
                url = row.get('URL', '').strip()
                name = row.get('Name', '').strip()
                last_id = row.get('Last_Post_ID', '').strip()
                
                if not url or not name:
                    print(f"⚠️ Ligne {i+1} ignorée (données manquantes)")
                    continue
                
                print(f"\n--- {i+1}/{total_profiles}: {name} ---")
                print(f"🔗 URL: {url}")
                print(f"🆔 Dernier ID connu: {last_id[:12] if last_id else 'Aucun'}...")
                
                # Vérification de la page
                result = self.check_linkedin_page(url, name)
                
                if result and result['status'] == 'success':
                    successful_checks += 1
                    current_id = result['id']
                    
                    print(f"🔍 ID actuel: {current_id[:12]}...")
                    
                    # Détection des changements
                    if last_id != current_id:
                        changes_detected += 1
                        print(f"🆕 CHANGEMENT DÉTECTÉ pour {name} !")
                        
                        # Envoi notification
                        if self.send_simple_email(result):
                            row['Last_Post_ID'] = current_id
                            changes_made = True
                            print("✅ Notification envoyée et données mises à jour")
                        else:
                            print("❌ Échec envoi notification")
                    else:
                        print("⚪ Aucun changement détecté")
                else:
                    print(f"❌ Échec vérification de {name}")
                
                # Pause entre vérifications
                if i < total_profiles - 1:
                    pause_time = 10 + (i % 3) * 2  # Pause variable
                    print(f"⏳ Pause de {pause_time}s...")
                    time.sleep(pause_time)
            
            # Sauvegarde finale
            if changes_made:
                if self.save_urls_to_csv(data):
                    print("\n💾 ✅ Données sauvegardées avec succès")
                else:
                    print("\n💾 ❌ Échec de la sauvegarde")
            
            # Résumé final
            print("\n" + "=" * 60)
            print("📊 RÉSUMÉ FINAL:")
            print(f"   • Profils vérifiés avec succès: {successful_checks}/{total_profiles}")
            print(f"   • Changements détectés: {changes_detected}")
            print(f"   • Notifications envoyées: {changes_detected if changes_made else 0}")
            print(f"   • Données mises à jour: {'Oui' if changes_made else 'Non'}")
            print(f"🏁 FIN - {datetime.now()}")
            print("=" * 60)
            
            return True
            
        except Exception as e:
            print(f"❌ ERREUR CRITIQUE: {e}")
            traceback.print_exc()
            return False

def main():
    """Fonction principale"""
    try:
        print("🎯" + "=" * 58 + "🎯")
        print("🤖 AGENT LINKEDIN - SURVEILLANCE AUTOMATIQUE")
        print("🎯" + "=" * 58 + "🎯")
        
        # Configuration
        csv_file = "linkedin_urls.csv"
        
        # Récupération des variables d'environnement
        email_config = {
            'sender_email': os.getenv('GMAIL_EMAIL'),
            'sender_password': os.getenv('GMAIL_APP_PASSWORD'),
            'recipient_email': os.getenv('RECIPIENT_EMAIL')
        }
        
        # Affichage configuration (masquée)
        print(f"📧 Email expéditeur: {email_config['sender_email']}")
        print(f"📧 Email destinataire: {email_config['recipient_email']}")
        print(f"🔑 Mot de passe app configuré: {'✅ Oui' if email_config['sender_password'] else '❌ Non'}")
        
        # Vérification variables obligatoires
        missing_vars = []
        for key, value in email_config.items():
            if not value:
                missing_vars.append(key)
        
        if missing_vars:
            print(f"\n❌ ERREUR: Variables d'environnement manquantes:")
            for var in missing_vars:
                print(f"   • {var}")
            print(f"\n💡 Solution: Configurez ces secrets dans GitHub:")
            print(f"   Settings → Secrets and variables → Actions")
            sys.exit(1)
        
        print(f"✅ Configuration validée\n")
        
        # Initialisation et lancement du monitoring
        monitor = LinkedInMonitor(csv_file, email_config)
        success = monitor.run_monitoring()
        
        # Code de sortie
        if success:
            print("🎉 AGENT TERMINÉ AVEC SUCCÈS")
            sys.exit(0)
        else:
            print("💥 ÉCHEC DE L'AGENT")
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n⏹️ Arrêt demandé par l'utilisateur")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 ERREUR FATALE NON GÉRÉE: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
