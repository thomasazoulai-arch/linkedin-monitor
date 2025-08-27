import requests
import pandas as pd
import json
import time
from datetime import datetime
import os
import re
import hashlib
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import sys
import traceback

class LinkedInMonitor:
    def __init__(self, excel_file_path, email_config):
        self.excel_file_path = excel_file_path
        self.email_config = email_config
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        print(f"✅ LinkedInMonitor initialisé avec le fichier: {excel_file_path}")
    
    def load_urls_from_excel(self):
        """Charge les URLs depuis le fichier Excel"""
        try:
            print(f"📁 Tentative de chargement du fichier: {self.excel_file_path}")
            
            # Vérifier si le fichier existe
            if not os.path.exists(self.excel_file_path):
                print(f"❌ ERREUR: Le fichier {self.excel_file_path} n'existe pas")
                print(f"📂 Fichiers présents dans le répertoire:")
                for file in os.listdir('.'):
                    print(f"   - {file}")
                return None
            
            # Charger le fichier Excel
            df = pd.read_excel(self.excel_file_path)
            print(f"✅ Fichier Excel chargé avec succès")
            print(f"📊 Nombre de lignes: {len(df)}")
            print(f"📊 Colonnes: {list(df.columns)}")
            
            # Vérifier les colonnes requises
            required_columns = ['URL', 'Name']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                print(f"❌ ERREUR: Colonnes manquantes: {missing_columns}")
                return None
            
            # Ajouter la colonne Last_Post_ID si elle n'existe pas
            if 'Last_Post_ID' not in df.columns:
                df['Last_Post_ID'] = ''
                print("➕ Colonne 'Last_Post_ID' ajoutée")
            
            print(f"📋 Profils à surveiller:")
            for idx, row in df.iterrows():
                print(f"   {idx+1}. {row['Name']} - {row['URL']}")
            
            return df
            
        except Exception as e:
            print(f"❌ ERREUR lors du chargement du fichier Excel: {e}")
            print(f"🔍 Détails de l'erreur:")
            traceback.print_exc()
            return None
    
    def save_urls_to_excel(self, df):
        """Sauvegarde les URLs mises à jour dans le fichier Excel"""
        try:
            print("💾 Sauvegarde du fichier Excel...")
            df.to_excel(self.excel_file_path, index=False)
            print("✅ Fichier Excel mis à jour avec succès")
            return True
        except Exception as e:
            print(f"❌ ERREUR lors de la sauvegarde: {e}")
            traceback.print_exc()
            return False
    
    def extract_post_info_from_html(self, html_content, profile_name):
        """Extrait les informations des posts depuis le HTML LinkedIn"""
        try:
            posts = []
            
            # Méthode simplifiée - cherche des patterns dans le HTML
            # Génère un hash basé sur une portion du contenu HTML pour détecter les changements
            content_sample = html_content[:5000] if len(html_content) > 5000 else html_content
            post_id = hashlib.md5(content_sample.encode('utf-8', errors='ignore')).hexdigest()[:12]
            
            # Extrait un échantillon de texte nettoyé
            text_content = re.sub(r'<[^>]+>', ' ', content_sample)
            text_content = ' '.join(text_content.split())[:200]
            
            posts.append({
                'id': post_id,
                'content': text_content,
                'profile': profile_name,
                'timestamp': datetime.now().isoformat(),
                'link': ''
            })
            
            print(f"📄 Post extrait pour {profile_name} (ID: {post_id})")
            return posts
            
        except Exception as e:
            print(f"❌ ERREUR lors de l'extraction pour {profile_name}: {e}")
            return []
    
    def scrape_linkedin_profile(self, url, profile_name):
        """Scrape une page LinkedIn pour récupérer les posts récents"""
        try:
            print(f"🌐 Scraping de {profile_name} ({url})...")
            
            # Ajoute un délai pour éviter le rate limiting
            time.sleep(3)
            
            response = requests.get(url, headers=self.headers, timeout=15)
            print(f"📡 Réponse HTTP: {response.status_code}")
            
            if response.status_code == 200:
                print(f"✅ Contenu récupéré ({len(response.text)} caractères)")
                posts = self.extract_post_info_from_html(response.text, profile_name)
                return posts
            else:
                print(f"❌ Erreur HTTP {response.status_code} pour {url}")
                return []
                
        except requests.exceptions.Timeout:
            print(f"⏰ Timeout lors du scraping de {url}")
            return []
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur de requête pour {url}: {e}")
            return []
        except Exception as e:
            print(f"❌ Erreur inattendue lors du scraping de {url}: {e}")
            traceback.print_exc()
            return []
    
    def create_html_email(self, post_info):
        """Crée le contenu HTML de l'email"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Veille LinkedIn - {post_info['profile']}</title>
            <style>
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    line-height: 1.6; 
                    color: #333; 
                    max-width: 600px; 
                    margin: 0 auto; 
                    padding: 20px;
                    background-color: #f9f9f9;
                }}
                .container {{ 
                    background-color: white; 
                    padding: 30px; 
                    border-radius: 10px; 
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{ 
                    background: linear-gradient(135deg, #0077b5, #004182); 
                    color: white; 
                    padding: 20px; 
                    text-align: center; 
                    margin: -30px -30px 30px -30px; 
                    border-radius: 10px 10px 0 0;
                }}
                .header h1 {{ 
                    margin: 0; 
                    font-size: 24px;
                }}
                .profile-name {{ 
                    color: #0077b5; 
                    font-size: 20px; 
                    font-weight: bold; 
                    margin-bottom: 15px;
                }}
                .post-content {{ 
                    background-color: #f8f9fa; 
                    padding: 20px; 
                    border-left: 4px solid #0077b5; 
                    border-radius: 5px; 
                    margin: 20px 0;
                }}
                .timestamp {{ 
                    color: #666; 
                    font-size: 14px; 
                    margin-top: 15px;
                }}
                .footer {{ 
                    margin-top: 30px; 
                    padding-top: 20px; 
                    border-top: 1px solid #eee; 
                    color: #666; 
                    font-size: 12px; 
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔔 Activité LinkedIn Détectée</h1>
                </div>
                
                <div class="profile-name">
                    👤 {post_info['profile']}
                </div>
                
                <div class="post-content">
                    <strong>Changement détecté :</strong><br>
                    {post_info['content'][:300]}{'...' if len(post_info['content']) > 300 else ''}
                </div>
                
                <div class="timestamp">
                    🕒 Détecté le : {datetime.fromisoformat(post_info['timestamp']).strftime('%d/%m/%Y à %H:%M')}
                </div>
                
                <div class="footer">
                    <p>📊 Système de veille LinkedIn automatisé</p>
                    <p>Change ID: {post_info['id']}</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html_content
    
    def send_email_notification(self, post_info):
        """Envoie une notification par email"""
        try:
            print(f"📧 Préparation de l'email pour {post_info['profile']}...")
            
            # Configuration de l'email
            sender_email = self.email_config['sender_email']
            sender_password = self.email_config['sender_password']
            recipient_email = self.email_config['recipient_email']
            
            print(f"📧 Expéditeur: {sender_email}")
            print(f"📧 Destinataire: {recipient_email}")
            
            # Création du message
            message = MimeMultipart("alternative")
            message["Subject"] = f"Veille LinkedIn - {post_info['profile']}"
            message["From"] = sender_email
            message["To"] = recipient_email
            
            # Contenu texte simple (fallback)
            text_content = f"""
            Changement détecté sur LinkedIn !
            
            Profil : {post_info['profile']}
            Détecté le : {datetime.fromisoformat(post_info['timestamp']).strftime('%d/%m/%Y à %H:%M')}
            
            Change ID: {post_info['id']}
            """
            
            # Contenu HTML
            html_content = self.create_html_email(post_info)
            
            # Création des parties du message
            part1 = MimeText(text_content, "plain")
            part2 = MimeText(html_content, "html")
            
            message.attach(part1)
            message.attach(part2)
            
            print("📡 Connexion au serveur SMTP Gmail...")
            
            # Envoi de l'email via Gmail SMTP
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                print("🔐 Authentification...")
                server.login(sender_email, sender_password)
                print("📤 Envoi de l'email...")
                server.sendmail(sender_email, recipient_email, message.as_string())
            
            print(f"✅ Email envoyé avec succès pour {post_info['profile']}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ ERREUR d'authentification SMTP: {e}")
            print("🔍 Vérifiez:")
            print("   - Que la 2FA est activée sur Gmail")
            print("   - Que le mot de passe d'application est correct")
            print("   - Que les secrets GitHub sont bien configurés")
            return False
        except Exception as e:
            print(f"❌ ERREUR lors de l'envoi de l'email: {e}")
            traceback.print_exc()
            return False
    
    def check_for_new_posts(self):
        """Fonction principale pour vérifier les nouveaux posts"""
        try:
            print(f"🚀 === DÉBUT DU MONITORING - {datetime.now()} ===")
            
            # Charge les URLs depuis Excel
            df = self.load_urls_from_excel()
            if df is None:
                print("❌ Impossible de charger le fichier Excel. Arrêt du programme.")
                return False
            
            new_posts_found = False
            
            for index, row in df.iterrows():
                url = row['URL']
                name = row['Name']
                last_post_id = row.get('Last_Post_ID', '')
                
                print(f"\n--- Vérification {index+1}/{len(df)}: {name} ---")
                
                # Vérification de l'URL
                if pd.isna(url) or not url.strip():
                    print(f"⚠️ URL vide pour {name}, passage au suivant")
                    continue
                
                # Scrape la page
                posts = self.scrape_linkedin_profile(url, name)
                
                if posts and len(posts) > 0:
                    current_latest_post_id = posts[0]['id']
                    
                    print(f"🔍 Dernier ID connu: '{last_post_id}'")
                    print(f"🔍 ID actuel: '{current_latest_post_id}'")
                    
                    if str(last_post_id).strip() != str(current_latest_post_id).strip():
                        print(f"🆕 CHANGEMENT détecté pour {name}!")
                        
                        # Envoie la notification par email
                        if self.send_email_notification(posts[0]):
                            # Met à jour l'ID du dernier post dans Excel
                            df.at[index, 'Last_Post_ID'] = current_latest_post_id
                            new_posts_found = True
                            print(f"✅ Notification envoyée et ID mis à jour pour {name}")
                        else:
                            print(f"❌ Échec de l'envoi de notification pour {name}")
                    else:
                        print(f"⚪ Aucun changement pour {name}")
                else:
                    print(f"❌ Impossible de récupérer le contenu pour {name}")
                
                # Pause entre les requêtes
                if index < len(df) - 1:  # Pas de pause après le dernier
                    print("⏳ Pause de 5 secondes...")
                    time.sleep(5)
            
            # Sauvegarde les modifications si nécessaire
            if new_posts_found:
                if self.save_urls_to_excel(df):
                    print("✅ Fichier Excel sauvegardé avec les nouveaux IDs")
                else:
                    print("❌ Erreur lors de la sauvegarde du fichier Excel")
            else:
                print("ℹ️ Aucun changement détecté, pas de mise à jour nécessaire")
            
            print(f"\n🏁 === FIN DU MONITORING - {datetime.now()} ===")
            return True
            
        except Exception as e:
            print(f"❌ ERREUR CRITIQUE dans check_for_new_posts: {e}")
            traceback.print_exc()
            return False

def main():
    try:
        print("🔧 === CONFIGURATION ===")
        
        # Configuration
        excel_file = "linkedin_urls.xlsx"
        
        # Configuration email depuis les variables d'environnement
        email_config = {
            'sender_email': os.getenv('GMAIL_EMAIL'),
            'sender_password': os.getenv('GMAIL_APP_PASSWORD'),
            'recipient_email': os.getenv('RECIPIENT_EMAIL')
        }
        
        print(f"📁 Fichier Excel: {excel_file}")
        print(f"📧 Email expéditeur: {email_config['sender_email']}")
        print(f"📧 Email destinataire: {email_config['recipient_email']}")
        print(f"🔑 Mot de passe configuré: {'Oui' if email_config['sender_password'] else 'Non'}")
        
        # Vérification des variables d'environnement
        missing_vars = [key for key, value in email_config.items() if not value]
        if missing_vars:
            print(f"❌ ERREUR: Variables d'environnement manquantes: {missing_vars}")
            print("🔍 Vérifiez que ces secrets sont configurés dans GitHub:")
            for var in missing_vars:
                if var == 'sender_email':
                    print(f"   - GMAIL_EMAIL")
                elif var == 'sender_password':
                    print(f"   - GMAIL_APP_PASSWORD")
                elif var == 'recipient_email':
                    print(f"   - RECIPIENT_EMAIL")
            sys.exit(1)
        
        # Crée l'instance du monitor
        monitor = LinkedInMonitor(excel_file, email_config)
        
        # Lance la vérification
        success = monitor.check_for_new_posts()
        
        if success:
            print("✅ Monitoring terminé avec succès")
            sys.exit(0)
        else:
            print("❌ Monitoring terminé avec des erreurs")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ ERREUR FATALE dans main(): {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
