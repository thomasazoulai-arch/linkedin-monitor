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
from email.mime.base import MimeBase
from email import encoders

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
    
    def load_urls_from_excel(self):
        """Charge les URLs depuis le fichier Excel"""
        try:
            df = pd.read_excel(self.excel_file_path)
            return df
        except Exception as e:
            print(f"Erreur lors du chargement du fichier Excel: {e}")
            return None
    
    def save_urls_to_excel(self, df):
        """Sauvegarde les URLs mises à jour dans le fichier Excel"""
        try:
            df.to_excel(self.excel_file_path, index=False)
            print("Fichier Excel mis à jour avec succès")
        except Exception as e:
            print(f"Erreur lors de la sauvegarde: {e}")
    
    def extract_post_info_from_html(self, html_content, profile_name):
        """Extrait les informations des posts depuis le HTML LinkedIn"""
        posts = []
        
        # Pattern pour trouver les posts récents (méthode basique)
        # LinkedIn change régulièrement sa structure, cette méthode est simplifiée
        post_patterns = [
            r'<div[^>]*class="[^"]*feed-shared-update-v2[^"]*"[^>]*>.*?</div>',
            r'<article[^>]*>.*?</article>',
        ]
        
        for pattern in post_patterns:
            matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                # Génère un ID unique basé sur le contenu du post
                post_id = hashlib.md5(match.encode()).hexdigest()[:12]
                
                # Extraction basique du texte (à améliorer selon la structure HTML)
                text_content = re.sub(r'<[^>]+>', ' ', match)
                text_content = ' '.join(text_content.split())[:300]
                
                # Extraction d'un éventuel lien vers le post
                post_link_match = re.search(r'href="([^"]*activity[^"]*)"', match)
                post_link = post_link_match.group(1) if post_link_match else ""
                if post_link and not post_link.startswith('http'):
                    post_link = f"https://www.linkedin.com{post_link}"
                
                posts.append({
                    'id': post_id,
                    'content': text_content,
                    'profile': profile_name,
                    'timestamp': datetime.now().isoformat(),
                    'link': post_link
                })
        
        return posts[:3]  # Retourne les 3 posts les plus récents
    
    def scrape_linkedin_profile(self, url, profile_name):
        """Scrape une page LinkedIn pour récupérer les posts récents"""
        try:
            # Ajoute un délai pour éviter le rate limiting
            time.sleep(2)
            
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                posts = self.extract_post_info_from_html(response.text, profile_name)
                return posts
            else:
                print(f"Erreur HTTP {response.status_code} pour {url}")
                return []
                
        except Exception as e:
            print(f"Erreur lors du scraping de {url}: {e}")
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
                .cta-button {{ 
                    display: inline-block; 
                    background-color: #0077b5; 
                    color: white; 
                    padding: 12px 25px; 
                    text-decoration: none; 
                    border-radius: 5px; 
                    margin-top: 20px;
                    font-weight: bold;
                }}
                .footer {{ 
                    margin-top: 30px; 
                    padding-top: 20px; 
                    border-top: 1px solid #eee; 
                    color: #666; 
                    font-size: 12px; 
                    text-align: center;
                }}
                .emoji {{ 
                    font-size: 18px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1><span class="emoji">🔔</span> Nouveau Post LinkedIn Détecté</h1>
                </div>
                
                <div class="profile-name">
                    <span class="emoji">👤</span> {post_info['profile']}
                </div>
                
                <div class="post-content">
                    <strong>Contenu du post :</strong><br>
                    {post_info['content'][:500]}{'...' if len(post_info['content']) > 500 else ''}
                </div>
                
                <div class="timestamp">
                    <span class="emoji">🕒</span> Détecté le : {datetime.fromisoformat(post_info['timestamp']).strftime('%d/%m/%Y à %H:%M')}
                </div>
                
                {f'<a href="{post_info["link"]}" class="cta-button">Voir le post sur LinkedIn</a>' if post_info.get('link') else ''}
                
                <div class="footer">
                    <p>📊 Système de veille LinkedIn automatisé</p>
                    <p>Post ID: {post_info['id']}</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html_content
    
    def send_email_notification(self, post_info):
        """Envoie une notification par email"""
        try:
            # Configuration de l'email
            sender_email = self.email_config['sender_email']
            sender_password = self.email_config['sender_password']
            recipient_email = self.email_config['recipient_email']
            
            # Création du message
            message = MimeMultipart("alternative")
            message["Subject"] = f"Veille LinkedIn - {post_info['profile']}"
            message["From"] = sender_email
            message["To"] = recipient_email
            
            # Contenu texte simple (fallback)
            text_content = f"""
            Nouveau post LinkedIn détecté !
            
            Profil : {post_info['profile']}
            Contenu : {post_info['content'][:200]}...
            Détecté le : {datetime.fromisoformat(post_info['timestamp']).strftime('%d/%m/%Y à %H:%M')}
            
            Post ID: {post_info['id']}
            """
            
            # Contenu HTML
            html_content = self.create_html_email(post_info)
            
            # Création des parties du message
            part1 = MimeText(text_content, "plain")
            part2 = MimeText(html_content, "html")
            
            message.attach(part1)
            message.attach(part2)
            
            # Envoi de l'email via Gmail SMTP
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient_email, message.as_string())
            
            print(f"Email envoyé avec succès pour {post_info['profile']}")
            return True
            
        except Exception as e:
            print(f"Erreur lors de l'envoi de l'email: {e}")
            return False
    
    def check_for_new_posts(self):
        """Fonction principale pour vérifier les nouveaux posts"""
        print(f"Début du monitoring - {datetime.now()}")
        
        # Charge les URLs depuis Excel
        df = self.load_urls_from_excel()
        if df is None:
            return
        
        new_posts_found = False
        
        for index, row in df.iterrows():
            url = row['URL']
            name = row['Name']
            last_post_id = row.get('Last_Post_ID', '')
            
            print(f"Vérification de {name}...")
            
            # Scrape la page
            posts = self.scrape_linkedin_profile(url, name)
            
            if posts:
                # Vérifie s'il y a de nouveaux posts
                current_latest_post_id = posts[0]['id']
                
                if last_post_id != current_latest_post_id:
                    print(f"Nouveau post détecté pour {name}!")
                    
                    # Envoie la notification par email
                    if self.send_email_notification(posts[0]):
                        # Met à jour l'ID du dernier post dans Excel
                        df.at[index, 'Last_Post_ID'] = current_latest_post_id
                        new_posts_found = True
                else:
                    print(f"Aucun nouveau post pour {name}")
            else:
                print(f"Impossible de récupérer les posts pour {name}")
        
        # Sauvegarde les modifications si nécessaire
        if new_posts_found:
            self.save_urls_to_excel(df)
        
        print("Monitoring terminé")

def main():
    # Configuration
    excel_file = "linkedin_urls.xlsx"  # Nom de votre fichier Excel
    
    # Configuration email depuis les variables d'environnement
    email_config = {
        'sender_email': os.getenv('GMAIL_EMAIL'),
        'sender_password': os.getenv('GMAIL_APP_PASSWORD'),
        'recipient_email': os.getenv('RECIPIENT_EMAIL')
    }
    
    # Vérification des variables d'environnement
    missing_vars = [key for key, value in email_config.items() if not value]
    if missing_vars:
        print(f"Erreur: Les variables d'environnement suivantes ne sont pas définies: {missing_vars}")
        return
    
    # Crée l'instance du monitor
    monitor = LinkedInMonitor(excel_file, email_config)
    
    # Lance la vérification
    monitor.check_for_new_posts()

if __name__ == "__main__":
    main()
