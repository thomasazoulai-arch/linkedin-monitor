#!/usr/bin/env python3
"""
LinkedIn Monitor Agent - Version Production
Expert Python avec validation complète des données
"""
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
from typing import Dict, List, Optional, Any

class LinkedInMonitor:
    """Agent de surveillance LinkedIn avec gestion d'erreurs robuste"""
    
    def __init__(self, csv_file_path: str, email_config: Dict[str, str]):
        self.csv_file_path = csv_file_path
        self.email_config = email_config
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        print(f"✅ LinkedInMonitor initialisé avec session persistante")
    
    def _safe_get_value(self, row: Dict[str, Any], key: str, default: str = '') -> str:
        """Récupération sécurisée d'une valeur de dictionnaire"""
        value = row.get(key)
        if value is None:
            return default
        return str(value).strip()
    
    def create_default_csv(self) -> Optional[List[Dict[str, str]]]:
        """Crée un fichier CSV par défaut avec validation"""
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
                },
                {
                    'URL': 'https://www.linkedin.com/company/google/',
                    'Name': 'Google',
                    'Last_Post_ID': ''
                }
            ]
            
            self._save_csv_data(default_data)
            print("✅ Fichier CSV par défaut créé")
            return default_data
            
        except Exception as e:
            print(f"❌ Erreur création CSV par défaut: {e}")
            return None

    def load_urls_from_csv(self) -> Optional[List[Dict[str, str]]]:
        """Charge et valide les URLs depuis le CSV avec gestion robuste des erreurs"""
        try:
            print(f"📁 Chargement du fichier: {self.csv_file_path}")
            
            if not os.path.exists(self.csv_file_path):
                print(f"❌ Fichier {self.csv_file_path} introuvable")
                return self.create_default_csv()
            
            # Lecture avec gestion multi-encodage
            data = self._read_csv_with_encoding()
            if not data:
                print("📂 Fichier vide ou illisible, création d'un fichier par défaut")
                return self.create_default_csv()
            
            # Validation et nettoyage des données
            cleaned_data = self._validate_and_clean_data(data)
            
            print(f"✅ {len(cleaned_data)} profils valides chargés")
            return cleaned_data
            
        except Exception as e:
            print(f"❌ Erreur chargement CSV: {e}")
            traceback.print_exc()
            return self.create_default_csv()
    
    def _read_csv_with_encoding(self) -> List[Dict[str, Any]]:
        """Lecture CSV avec test de multiples encodages"""
        encodings = ['utf-8-sig', 'utf-8', 'iso-8859-1', 'cp1252', 'latin1']
        
        for encoding in encodings:
            try:
                print(f"🔄 Test encodage: {encoding}")
                data = []
                with open(self.csv_file_path, 'r', encoding=encoding, newline='') as file:
                    reader = csv.DictReader(file)
                    for row_num, row in enumerate(reader, 1):
                        if row:  # Ignore les lignes vides
                            # Nettoyage préventif des valeurs None
                            cleaned_row = {}
                            for key, value in row.items():
                                if key:  # Ignore les clés None/vides
                                    cleaned_row[key.strip()] = value if value is not None else ''
                            if cleaned_row:
                                data.append(cleaned_row)
                        
                print(f"✅ Succès avec {encoding} - {len(data)} lignes lues")
                return data
                
            except UnicodeDecodeError as e:
                print(f"❌ Échec {encoding}: {e}")
                continue
            except Exception as e:
                print(f"❌ Erreur lecture {encoding}: {e}")
                continue
        
        print("❌ Impossible de lire avec tous les encodages")
        return []
    
    def _validate_and_clean_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Validation et nettoyage robuste des données CSV"""
        cleaned_data = []
        required_fields = ['URL', 'Name']
        
        for i, row in enumerate(raw_data):
            try:
                # Extraction sécurisée des valeurs
                url = self._safe_get_value(row, 'URL')
                name = self._safe_get_value(row, 'Name')
                last_post_id = self._safe_get_value(row, 'Last_Post_ID', '')
                
                # Validation des champs obligatoires
                if not url or not name:
                    print(f"⚠️ Ligne {i+1} ignorée: URL ou Name manquant")
                    continue
                
                # Validation de l'URL
                if not self._is_valid_linkedin_url(url):
                    print(f"⚠️ Ligne {i+1} ignorée: URL LinkedIn invalide")
                    continue
                
                # Construction de l'enregistrement nettoyé
                clean_row = {
                    'URL': url,
                    'Name': name,
                    'Last_Post_ID': last_post_id
                }
                
                cleaned_data.append(clean_row)
                print(f"✅ Ligne {i+1}: {name} validé")
                
            except Exception as e:
                print(f"❌ Erreur ligne {i+1}: {e}")
                continue
        
        return cleaned_data
    
    def _is_valid_linkedin_url(self, url: str) -> bool:
        """Validation d'URL LinkedIn"""
        linkedin_patterns = [
            r'^https://www\.linkedin\.com/company/[^/]+/?',
            r'^https://www\.linkedin\.com/in/[^/]+/?',
            r'^https://www\.linkedin\.com/company/[^/]+/posts/'
        ]
        
        return any(re.match(pattern, url) for pattern in linkedin_patterns)
    
    def _save_csv_data(self, data: List[Dict[str, str]]) -> bool:
        """Sauvegarde sécurisée du CSV"""
        try:
            if not data:
                print("⚠️ Aucune donnée à sauvegarder")
                return False
            
            fieldnames = ['URL', 'Name', 'Last_Post_ID']
            
            # Sauvegarde avec UTF-8 BOM pour Excel
            with open(self.csv_file_path, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                
                for row in data:
                    # Assure que tous les champs existent
                    safe_row = {
                        'URL': self._safe_get_value(row, 'URL'),
                        'Name': self._safe_get_value(row, 'Name'),
                        'Last_Post_ID': self._safe_get_value(row, 'Last_Post_ID')
                    }
                    writer.writerow(safe_row)
            
            print("✅ CSV sauvegardé avec succès")
            return True
            
        except Exception as e:
            print(f"❌ Erreur sauvegarde CSV: {e}")
            return False
    
    def extract_linkedin_content_info(self, html_content: str) -> Dict[str, Any]:
        """Extraction intelligente du contenu LinkedIn"""
        try:
            info = {
                'activity_detected': False,
                'content_hash': '',
                'activity_score': 0,
                'post_indicators': 0,
                'engagement_found': False
            }
            
            # Patterns LinkedIn sophistiqués
            patterns = {
                'posts': [
                    r'feed-shared-update-v2',
                    r'posted this',
                    r'shared this',
                    r'published this'
                ],
                'engagement': [
                    r'(\d+)\s*likes?',
                    r'(\d+)\s*comments?',
                    r'(\d+)\s*reactions?',
                    r'(\d+)\s*shares?'
                ],
                'activity': [
                    r'activity-\w+',
                    r'feed-shared-actor',
                    r'update-components-text'
                ]
            }
            
            activity_score = 0
            
            # Analyse des patterns
            for category, pattern_list in patterns.items():
                for pattern in pattern_list:
                    matches = re.findall(pattern, html_content, re.IGNORECASE)
                    if matches:
                        if category == 'posts':
                            info['post_indicators'] += len(matches)
                            activity_score += len(matches) * 3
                        elif category == 'engagement':
                            info['engagement_found'] = True
                            activity_score += len(matches) * 2
                        elif category == 'activity':
                            activity_score += len(matches)
            
            info['activity_score'] = activity_score
            info['activity_detected'] = activity_score > 0
            
            # Hash de contenu amélioré
            significant_content = html_content[:12000]  # Plus de contenu
            content_with_score = significant_content + str(activity_score)
            info['content_hash'] = hashlib.sha256(
                content_with_score.encode('utf-8', errors='ignore')
            ).hexdigest()[:20]  # Hash plus long
            
            return info
            
        except Exception as e:
            print(f"❌ Erreur extraction contenu: {e}")
            return {
                'activity_detected': False,
                'content_hash': 'error',
                'activity_score': 0,
                'post_indicators': 0,
                'engagement_found': False
            }
    
    def check_linkedin_profile(self, url: str, name: str) -> Optional[Dict[str, Any]]:
        """Vérification robuste d'un profil LinkedIn"""
        try:
            print(f"🌐 Analyse de {name}...")
            
            # Pause anti-detection variable
            time.sleep(8 + (hash(name) % 5))
            
            # Préparation de l'URL optimale
            check_url = self._prepare_linkedin_url(url)
            
            # Requête avec retry
            response = self._make_request_with_retry(check_url, max_retries=2)
            
            if not response:
                return None
            
            if response.status_code == 200:
                print(f"✅ Page accessible ({len(response.text):,} caractères)")
                
                # Extraction avancée du contenu
                content_info = self.extract_linkedin_content_info(response.text)
                
                result = {
                    'id': content_info['content_hash'],
                    'name': name,
                    'url': check_url,
                    'original_url': url,
                    'timestamp': datetime.now().isoformat(),
                    'activity_detected': content_info['activity_detected'],
                    'activity_score': content_info['activity_score'],
                    'post_indicators': content_info['post_indicators'],
                    'engagement_found': content_info['engagement_found'],
                    'status': 'success'
                }
                
                print(f"✅ Hash: {result['id']}")
                print(f"📊 Score d'activité: {content_info['activity_score']}")
                print(f"📝 Posts détectés: {content_info['post_indicators']}")
                
                return result
                
            else:
                print(f"❌ HTTP {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Erreur vérification {name}: {e}")
            return None
    
    def _prepare_linkedin_url(self, url: str) -> str:
        """Préparation optimale de l'URL LinkedIn"""
        if 'company' in url and 'posts' not in url:
            if not url.endswith('/'):
                url += '/'
            if not url.endswith('posts/'):
                url += 'posts/'
        return url
    
    def _make_request_with_retry(self, url: str, max_retries: int = 2) -> Optional[requests.Response]:
        """Requête HTTP avec retry et gestion d'erreurs"""
        for attempt in range(max_retries + 1):
            try:
                response = self.session.get(url, timeout=30)
                return response
            except requests.exceptions.Timeout:
                print(f"⏰ Timeout tentative {attempt + 1}")
                if attempt < max_retries:
                    time.sleep(5 * (attempt + 1))
                    continue
            except requests.exceptions.RequestException as e:
                print(f"❌ Erreur requête: {e}")
                if attempt < max_retries:
                    time.sleep(3)
                    continue
        return None
    
    def send_notification_email(self, profile_info: Dict[str, Any]) -> bool:
        """Envoi d'email de notification robuste"""
        try:
            print(f"📧 Préparation notification pour {profile_info['name']}...")
            
            # Configuration email
            sender_email = self.email_config['sender_email']
            sender_password = self.email_config['sender_password']
            recipient_email = self.email_config['recipient_email']
            
            # Formatage de la date
            try:
                dt = datetime.fromisoformat(profile_info['timestamp'])
                date_str = dt.strftime('%d/%m/%Y à %H:%M')
            except:
                date_str = "Date inconnue"
            
            # Construction du message
            subject = f"🔔 LinkedIn Alert - {profile_info['name']}"
            
            body = self._build_email_body(profile_info, date_str)
            
            # Message RFC 2822 compliant
            email_message = f"""From: {sender_email}
To: {recipient_email}
Subject: {subject}
Content-Type: text/plain; charset=utf-8
MIME-Version: 1.0

{body}"""
            
            # Envoi SMTP sécurisé
            success = self._send_smtp_email(sender_email, sender_password, recipient_email, email_message)
            
            if success:
                print("✅ Email envoyé avec succès")
            return success
            
        except Exception as e:
            print(f"❌ Erreur notification email: {e}")
            return False
    
    def _build_email_body(self, profile_info: Dict[str, Any], date_str: str) -> str:
        """Construction du corps de l'email"""
        return f"""🔔 NOUVELLE ACTIVITÉ LINKEDIN DÉTECTÉE

📋 DÉTAILS:
• Profil/Entreprise: {profile_info['name']}
• URL: {profile_info['url']}
• Détection: {date_str}
• ID de suivi: {profile_info['id']}

📊 ANALYSE:
• Score d'activité: {profile_info['activity_score']}
• Posts détectés: {profile_info['post_indicators']}
• Engagement trouvé: {'Oui' if profile_info['engagement_found'] else 'Non'}

🤖 Agent LinkedIn automatisé
Surveillance 24h/24 - 7j/7

Pour consulter le contenu, cliquez sur l'URL ci-dessus.
---
Système de veille professionnel"""
    
    def _send_smtp_email(self, sender: str, password: str, recipient: str, message: str) -> bool:
        """Envoi SMTP sécurisé avec gestion d'erreurs"""
        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(sender, password)
                server.sendmail(sender, [recipient], message.encode('utf-8'))
            return True
        except smtplib.SMTPAuthenticationError:
            print("❌ Erreur authentification Gmail - vérifiez le mot de passe d'application")
        except smtplib.SMTPException as e:
            print(f"❌ Erreur SMTP: {e}")
        except Exception as e:
            print(f"❌ Erreur envoi: {e}")
        return False
    
    def run_monitoring_cycle(self) -> bool:
        """Cycle principal de monitoring avec gestion complète des erreurs"""
        try:
            print("=" * 70)
            print(f"🚀 DÉBUT CYCLE MONITORING - {datetime.now()}")
            print("=" * 70)
            
            # Chargement et validation des données
            data = self.load_urls_from_csv()
            if not data:
                print("❌ Impossible de charger les profils")
                return False
            
            # Initialisation des compteurs
            stats = {
                'total': len(data),
                'successful_checks': 0,
                'changes_detected': 0,
                'notifications_sent': 0,
                'errors': 0
            }
            
            print(f"📋 {stats['total']} profils à analyser")
            
            # Traitement de chaque profil
            changes_made = False
            
            for i, row in enumerate(data):
                try:
                    result = self._process_single_profile(row, i + 1, stats['total'])
                    
                    if result['success']:
                        stats['successful_checks'] += 1
                        
                        if result['changed']:
                            stats['changes_detected'] += 1
                            row['Last_Post_ID'] = result['new_id']
                            changes_made = True
                            
                            if result['notification_sent']:
                                stats['notifications_sent'] += 1
                    else:
                        stats['errors'] += 1
                    
                    # Pause variable entre profils
                    if i < len(data) - 1:
                        pause = 12 + (i % 4) * 3
                        print(f"⏳ Pause {pause}s...")
                        time.sleep(pause)
                
                except Exception as e:
                    print(f"❌ Erreur traitement profil {i+1}: {e}")
                    stats['errors'] += 1
                    continue
            
            # Sauvegarde des modifications
            if changes_made:
                if self._save_csv_data(data):
                    print("\n💾 ✅ Modifications sauvegardées")
                else:
                    print("\n💾 ❌ Échec sauvegarde")
            
            # Rapport final
            self._print_final_report(stats)
            
            return stats['successful_checks'] > 0
            
        except Exception as e:
            print(f"❌ ERREUR CRITIQUE CYCLE: {e}")
            traceback.print_exc()
            return False
    
    def _process_single_profile(self, row: Dict[str, str], index: int, total: int) -> Dict[str, Any]:
        """Traitement sécurisé d'un profil individuel"""
        result = {
            'success': False,
            'changed': False,
            'notification_sent': False,
            'new_id': ''
        }
        
        try:
            # Extraction sécurisée des données
            url = self._safe_get_value(row, 'URL')
            name = self._safe_get_value(row, 'Name')
            last_id = self._safe_get_value(row, 'Last_Post_ID')
            
            if not url or not name:
                print(f"⚠️ Profil {index}/{total}: Données incomplètes")
                return result
            
            print(f"\n--- {index}/{total}: {name} ---")
            print(f"🔗 URL: {url}")
            print(f"🆔 Dernier ID: {last_id[:15]}..." if last_id else "🆔 Aucun ID précédent")
            
            # Vérification du profil
            profile_result = self.check_linkedin_profile(url, name)
            
            if profile_result and profile_result['status'] == 'success':
                result['success'] = True
                current_id = profile_result['id']
                result['new_id'] = current_id
                
                print(f"🔍 ID actuel: {current_id[:15]}...")
                
                # Détection des changements
                if last_id != current_id:
                    result['changed'] = True
                    print(f"🆕 CHANGEMENT DÉTECTÉ pour {name}!")
                    
                    # Envoi notification
                    if self.send_notification_email(profile_result):
                        result['notification_sent'] = True
                        print("✅ Notification envoyée")
                    else:
                        print("❌ Échec notification")
                else:
                    print("⚪ Aucun changement")
            else:
                print(f"❌ Échec vérification {name}")
            
            return result
            
        except Exception as e:
            print(f"❌ Erreur traitement {name if 'name' in locals() else 'profil'}: {e}")
            return result
    
    def _print_final_report(self, stats: Dict[str, int]) -> None:
        """Affichage du rapport final"""
        print("\n" + "=" * 70)
        print("📊 RAPPORT FINAL DE MONITORING")
        print("=" * 70)
        print(f"   📋 Profils analysés: {stats['successful_checks']}/{stats['total']}")
        print(f"   🆕 Changements détectés: {stats['changes_detected']}")
        print(f"   📧 Notifications envoyées: {stats['notifications_sent']}")
        print(f"   ❌ Erreurs rencontrées: {stats['errors']}")
        
        success_rate = (stats['successful_checks'] / stats['total']) * 100 if stats['total'] > 0 else 0
        print(f"   📈 Taux de succès: {success_rate:.1f}%")
        
        print(f"\n🏁 FIN - {datetime.now()}")
        print("=" * 70)

def validate_environment() -> Dict[str, str]:
    """Validation complète de l'environnement"""
    print("🔧 Validation de l'environnement...")
    
    email_config = {
        'sender_email': os.getenv('GMAIL_EMAIL', ''),
        'sender_password': os.getenv('GMAIL_APP_PASSWORD', ''),
        'recipient_email': os.getenv('RECIPIENT_EMAIL', '')
    }
    
    # Affichage configuration
    print(f"📧 Email expéditeur: {email_config['sender_email']}")
    print(f"📧 Email destinataire: {email_config['recipient_email']}")
    print(f"🔑 Mot de passe configuré: {'✅ Oui' if email_config['sender_password'] else '❌ Non'}")
    
    # Validation
    missing_vars = [key for key, value in email_config.items() if not value]
    
    if missing_vars:
        print(f"\n❌ VARIABLES MANQUANTES:")
        for var in missing_vars:
            print(f"   • {var}")
        print(f"\n💡 SOLUTION: Configurez dans GitHub Secrets:")
        print(f"   Repository → Settings → Secrets and variables → Actions")
        raise ValueError("Configuration incomplète")
    
    print("✅ Environnement validé")
    return email_config

def main() -> None:
    """Point d'entrée principal avec gestion d'erreurs experte"""
    try:
        print("🎯" + "=" * 68 + "🎯")
        print("🤖 LINKEDIN MONITORING AGENT - VERSION PRODUCTION")
        print("🎯" + "=" * 68 + "🎯")
        
        # Validation environnement
        email_config = validate_environment()
        
        # Initialisation de l'agent
        csv_file = "linkedin_urls.csv"
        monitor = LinkedInMonitor(csv_file, email_config)
        
        # Lancement du cycle de monitoring
        success = monitor.run_monitoring_cycle()
        
        # Code de retour
        if success:
            print("🎉 AGENT TERMINÉ AVEC SUCCÈS")
            sys.exit(0)
        else:
            print("💥 ÉCHEC CRITIQUE DE L'AGENT")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n⏹️ Arrêt demandé par utilisateur")
        sys.exit(130)  # Code standard pour interruption clavier
    except Exception as e:
        print(f"\n💥 ERREUR FATALE: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
