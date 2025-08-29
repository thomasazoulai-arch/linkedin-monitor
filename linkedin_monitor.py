#!/usr/bin/env python3
"""
LinkedIn Monitor Agent - Version Production Améliorée
Fonctionnalités:
- Email groupé pour tous les nouveaux posts
- Extraction directe des liens et métadonnées des posts
- Descriptions automatiques des posts
"""
import requests
import csv
import time
import json
import hashlib
import smtplib
import sys
import traceback
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, NamedTuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class PostData(NamedTuple):
    """Structure pour un nouveau post détecté"""
    profile_name: str
    post_title: str
    post_description: str
    post_url: str
    detection_time: str


class ProfileData:
    """Structure pour un profil LinkedIn"""
    
    def __init__(self, url: str, name: str, last_post_id: str = "", error_count: int = 0):
        self.url = url.strip()
        self.name = name.strip() 
        self.last_post_id = last_post_id.strip()
        self.error_count = error_count
        self.last_check = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, str]:
        return {
            'URL': self.url,
            'Name': self.name, 
            'Last_Post_ID': self.last_post_id,
            'Error_Count': str(self.error_count)
        }


class PostExtractor:
    """Extracteur de données détaillées des posts LinkedIn"""
    
    @staticmethod
    def extract_posts_data(html_content: str, profile_url: str, profile_name: str) -> List[PostData]:
        """Extraction des données complètes des posts"""
        try:
            posts_data = []
            
            # Patterns pour identifier les posts individuels
            post_patterns = [
                r'<div[^>]*data-urn[^>]*urn:li:activity:(\d+)[^>]*>(.*?)</div(?:\s[^>]*)?>(?=<div[^>]*data-urn|$)',
                r'<article[^>]*data-id[^>]*="(\d+)"[^>]*>(.*?)</article>',
                r'<div[^>]*feed-shared-update-v2[^>]*id="([^"]+)"[^>]*>(.*?)</div(?:\s[^>]*)?>(?=<div[^>]*feed-shared-update-v2|$)'
            ]
            
            for pattern in post_patterns:
                matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
                
                for post_id, post_content in matches[:5]:  # Limiter aux 5 derniers posts
                    post_data = PostExtractor._parse_single_post(
                        post_id, post_content, profile_url, profile_name
                    )
                    if post_data:
                        posts_data.append(post_data)
            
            # Si aucun post spécifique trouvé, essayer une approche alternative
            if not posts_data:
                posts_data = PostExtractor._fallback_extraction(html_content, profile_url, profile_name)
            
            return posts_data[:3]  # Limiter à 3 posts max par profile
            
        except Exception as e:
            print(f"❌ Erreur extraction posts: {e}")
            return []
    
    @staticmethod
    def _parse_single_post(post_id: str, post_html: str, profile_url: str, profile_name: str) -> Optional[PostData]:
        """Parse un post individuel"""
        try:
            # Extraction du titre
            title = PostExtractor._extract_title(post_html)
            
            # Extraction de la description
            description = PostExtractor._extract_description(post_html)
            
            # Construction de l'URL directe du post
            post_url = PostExtractor._build_post_url(post_id, profile_url)
            
            # Validation des données minimales
            if not title and not description:
                return None
            
            return PostData(
                profile_name=profile_name,
                post_title=title or "Nouveau post",
                post_description=description or "Nouvelle publication détectée",
                post_url=post_url,
                detection_time=datetime.now().strftime('%d/%m/%Y à %H:%M')
            )
            
        except Exception as e:
            print(f"❌ Erreur parse post {post_id}: {e}")
            return None
    
    @staticmethod
    def _extract_title(html: str) -> str:
        """Extraction du titre/première ligne du post"""
        title_patterns = [
            r'<span[^>]*update-components-text[^>]*aria-hidden="true"[^>]*>(.*?)</span>',
            r'<div[^>]*feed-shared-text[^>]*>(.*?)</div>',
            r'<h3[^>]*>(.*?)</h3>',
            r'<strong[^>]*>(.*?)</strong>',
            r'<p[^>]*class="[^"]*update-components[^"]*"[^>]*>(.*?)</p>'
        ]
        
        for pattern in title_patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            if matches:
                title = PostExtractor._clean_html_text(matches[0])
                if len(title.strip()) > 10:  # Titre significatif
                    # Limiter à la première phrase ou 100 caractères
                    sentences = re.split(r'[.!?]\s+', title)
                    first_sentence = sentences[0].strip()
                    return first_sentence[:100] + "..." if len(first_sentence) > 100 else first_sentence
        
        return ""
    
    @staticmethod
    def _extract_description(html: str) -> str:
        """Extraction et génération d'une description du post"""
        content_patterns = [
            r'<span[^>]*update-components-text[^>]*>(.*?)</span>',
            r'<div[^>]*feed-shared-text[^>]*>(.*?)</div>',
            r'<p[^>]*>(.*?)</p>'
        ]
        
        full_text = ""
        for pattern in content_patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                clean_text = PostExtractor._clean_html_text(match)
                if len(clean_text.strip()) > 20:
                    full_text += " " + clean_text
        
        if not full_text.strip():
            return "Nouvelle publication LinkedIn"
        
        # Génération d'une description intelligente
        return PostExtractor._generate_smart_description(full_text.strip())
    
    @staticmethod
    def _generate_smart_description(text: str) -> str:
        """Génère une description intelligente de 1-2 lignes"""
        # Nettoyer et normaliser le texte
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Si le texte est court, le retourner tel quel
        if len(text) <= 120:
            return text
        
        # Chercher une phrase complète de taille raisonnable
        sentences = re.split(r'[.!?]+\s*', text)
        for sentence in sentences:
            if 20 <= len(sentence.strip()) <= 120:
                return sentence.strip() + "."
        
        # Fallback: premiers mots avec coupure intelligente
        words = text.split()
        description = ""
        for word in words:
            if len(description + " " + word) <= 120:
                description += " " + word
            else:
                break
        
        return description.strip() + "..." if description else "Post LinkedIn intéressant"
    
    @staticmethod
    def _build_post_url(post_id: str, profile_url: str) -> str:
        """Construction de l'URL directe du post"""
        try:
            # Nettoyer l'ID
            clean_id = re.sub(r'[^0-9]', '', str(post_id))
            
            if '/company/' in profile_url:
                # URL pour les pages entreprise
                company_name = re.search(r'/company/([^/]+)', profile_url)
                if company_name and clean_id:
                    return f"https://www.linkedin.com/feed/update/urn:li:activity:{clean_id}"
            
            elif '/in/' in profile_url:
                # URL pour les profils personnels
                if clean_id:
                    return f"https://www.linkedin.com/feed/update/urn:li:activity:{clean_id}"
            
            # Fallback vers le profil
            return profile_url.rstrip('/posts').rstrip('/')
            
        except Exception:
            return profile_url
    
    @staticmethod
    def _fallback_extraction(html: str, profile_url: str, profile_name: str) -> List[PostData]:
        """Méthode de fallback si l'extraction standard échoue"""
        try:
            # Recherche de contenu général
            general_patterns = [
                r'<span[^>]*>([^<]{50,200})</span>',
                r'<p[^>]*>([^<]{30,150})</p>'
            ]
            
            posts_found = []
            for pattern in general_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for i, match in enumerate(matches[:2]):  # Max 2 posts
                    clean_text = PostExtractor._clean_html_text(match)
                    if len(clean_text.strip()) > 30:
                        posts_found.append(PostData(
                            profile_name=profile_name,
                            post_title="Nouvelle activité",
                            post_description=clean_text[:120] + "...",
                            post_url=profile_url,
                            detection_time=datetime.now().strftime('%d/%m/%Y à %H:%M')
                        ))
                        break
            
            return posts_found
            
        except Exception:
            return []
    
    @staticmethod
    def _clean_html_text(html_text: str) -> str:
        """Nettoyage du texte HTML"""
        if not html_text:
            return ""
        
        # Suppression des balises HTML
        text = re.sub(r'<[^>]+>', '', html_text)
        
        # Décodage des entités HTML courantes
        html_entities = {
            '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"',
            '&#39;': "'", '&nbsp;': ' ', '&hellip;': '...'
        }
        
        for entity, char in html_entities.items():
            text = text.replace(entity, char)
        
        # Nettoyage des espaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text


class GroupedEmailNotifier:
    """Gestionnaire d'email groupé pour plusieurs posts"""
    
    def __init__(self, sender_email: str, sender_password: str, recipient_email: str):
        self.sender_email = sender_email
        self.sender_password = sender_password  
        self.recipient_email = recipient_email
    
    def send_grouped_notification(self, all_new_posts: List[PostData]) -> bool:
        """Envoi d'une notification groupée pour tous les nouveaux posts"""
        try:
            if not all_new_posts:
                print("ℹ️ Aucun nouveau post à notifier")
                return True
            
            # Création du message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            # Sujet dynamique
            post_count = len(all_new_posts)
            profiles_count = len(set(post.profile_name for post in all_new_posts))
            msg['Subject'] = f"🔔 LinkedIn Alert - {post_count} nouveau{'x' if post_count > 1 else ''} post{'s' if post_count > 1 else ''} de {profiles_count} profile{'s' if profiles_count > 1 else ''}"
            
            # Contenu texte
            text_content = self._build_grouped_text_message(all_new_posts)
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            
            # Contenu HTML
            html_content = self._build_grouped_html_message(all_new_posts)
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Envoi SMTP
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            print(f"✅ Email groupé envoyé: {post_count} posts de {profiles_count} profiles")
            return True
            
        except Exception as e:
            print(f"❌ Erreur envoi email groupé: {e}")
            return False
    
    def _build_grouped_text_message(self, posts: List[PostData]) -> str:
        """Construction du message texte groupé"""
        content = f"""🔔 NOUVELLES ACTIVITÉS LINKEDIN DÉTECTÉES

📅 Rapport du {datetime.now().strftime('%d/%m/%Y à %H:%M UTC')}
📊 {len(posts)} nouveau{'x' if len(posts) > 1 else ''} post{'s' if len(posts) > 1 else ''} détecté{'s' if len(posts) > 1 else ''}

"""
        
        # Grouper par profile
        profiles_posts = {}
        for post in posts:
            if post.profile_name not in profiles_posts:
                profiles_posts[post.profile_name] = []
            profiles_posts[post.profile_name].append(post)
        
        # Générer le contenu pour chaque profile
        for profile_name, profile_posts in profiles_posts.items():
            content += f"👤 PROFILE: {profile_name}\n"
            content += "─" * 50 + "\n"
            
            for i, post in enumerate(profile_posts, 1):
                content += f"""
📝 POST #{i}:
   Titre: {post.post_title}
   Description: {post.post_description}
   URL: {post.post_url}
   Détecté: {post.detection_time}

"""
            content += "\n"
        
        content += """
🤖 Système de veille automatisé LinkedIn
Agent LinkedIn Monitor - Surveillance 24h/24

---
Pour configurer ou modifier cette veille, consultez votre repository GitHub.
"""
        
        return content
    
    def _build_grouped_html_message(self, posts: List[PostData]) -> str:
        """Construction du message HTML groupé"""
        post_count = len(posts)
        profiles_count = len(set(post.profile_name for post in posts))
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>LinkedIn Alert - Posts Groupés</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #0077b5, #005885); color: white; padding: 25px; border-radius: 10px; text-align: center; margin-bottom: 20px; }}
        .stats {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: center; }}
        .profile-section {{ background: #ffffff; border-left: 4px solid #0077b5; margin: 20px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        .post-card {{ background: #f8f9fa; margin: 15px 0; padding: 18px; border-radius: 8px; border-left: 3px solid #28a745; }}
        .post-title {{ font-weight: bold; color: #2c3e50; font-size: 16px; margin-bottom: 8px; }}
        .post-description {{ color: #555; font-style: italic; margin-bottom: 10px; line-height: 1.5; }}
        .post-url {{ margin: 10px 0; }}
        .post-meta {{ color: #666; font-size: 12px; }}
        .cta-button {{ background: #0077b5; color: white; padding: 12px 25px; text-decoration: none; border-radius: 25px; display: inline-block; font-weight: bold; margin: 10px 5px; }}
        .footer {{ text-align: center; font-size: 12px; color: #666; line-height: 1.4; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; }}
    </style>
</head>
<body>
    <div class="header">
        <h1 style="margin: 0; font-size: 28px;">🔔 Nouvelles Activités LinkedIn</h1>
        <p style="margin: 10px 0 0 0; opacity: 0.9; font-size: 16px;">Rapport groupé de veille</p>
    </div>
    
    <div class="stats">
        <h2 style="color: #0077b5; margin: 0 0 10px 0;">📊 Résumé</h2>
        <p style="margin: 5px; font-size: 18px;"><strong>{post_count}</strong> nouveau{'x' if post_count > 1 else ''} post{'s' if post_count > 1 else ''} de <strong>{profiles_count}</strong> profile{'s' if profiles_count > 1 else ''}</p>
        <p style="margin: 5px; color: #666;">Détection: {datetime.now().strftime('%d/%m/%Y à %H:%M UTC')}</p>
    </div>
"""
        
        # Grouper par profile
        profiles_posts = {}
        for post in posts:
            if post.profile_name not in profiles_posts:
                profiles_posts[post.profile_name] = []
            profiles_posts[post.profile_name].append(post)
        
        # Générer le HTML pour chaque profile
        for profile_name, profile_posts in profiles_posts.items():
            html += f"""
    <div class="profile-section">
        <h2 style="color: #0077b5; margin-top: 0; display: flex; align-items: center;">
            <span style="margin-right: 10px;">👤</span> {profile_name}
            <span style="background: #0077b5; color: white; padding: 4px 12px; border-radius: 15px; font-size: 12px; margin-left: auto;">
                {len(profile_posts)} post{'s' if len(profile_posts) > 1 else ''}
            </span>
        </h2>
"""
            
            for i, post in enumerate(profile_posts, 1):
                html += f"""
        <div class="post-card">
            <div class="post-title">📝 {post.post_title}</div>
            <div class="post-description">"{post.post_description}"</div>
            <div class="post-url">
                <a href="{post.post_url}" class="cta-button" target="_blank">👀 Voir le post</a>
            </div>
            <div class="post-meta">📅 Détecté le {post.detection_time}</div>
        </div>
"""
            
            html += "    </div>\n"
        
        html += """
    <div style="text-align: center; margin: 30px 0;">
        <p style="color: #0077b5; font-size: 16px; font-weight: bold;">🎯 Ne manquez aucune opportunité !</p>
        <p style="color: #555;">Votre système de veille LinkedIn travaille 24h/24 pour vous tenir informé</p>
    </div>
    
    <div class="footer">
        <p>🤖 <strong>LinkedIn Monitor Agent - Version Groupée</strong></p>
        <p>Surveillance automatisée • Notifications intelligentes • Alertes en temps réel</p>
        <p style="margin-top: 15px;">
            <em>Système de veille professionnel développé pour optimiser votre networking LinkedIn</em>
        </p>
    </div>
</body>
</html>
"""
        
        return html


class ContentAnalyzer:
    """Analyseur de contenu LinkedIn avec extraction détaillée"""
    
    @staticmethod
    def analyze_content_with_posts(html_content: str, profile_url: str, profile_name: str) -> Dict[str, Any]:
        """Analyse du contenu avec extraction des posts"""
        try:
            # Analyse générale (existante)
            basic_analysis = ContentAnalyzer._basic_analysis(html_content)
            
            # Extraction des posts détaillés (nouveau)
            posts_data = PostExtractor.extract_posts_data(html_content, profile_url, profile_name)
            
            # Génération du hash basé sur les posts récents
            content_hash = ContentAnalyzer._generate_posts_hash(posts_data)
            
            return {
                'content_hash': content_hash,
                'activity_score': basic_analysis['activity_score'],
                'post_count': len(posts_data),
                'posts_data': posts_data,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Erreur analyse contenu détaillée: {e}")
            return {
                'content_hash': f"error_{hash(html_content[:1000]) if html_content else 'empty'}",
                'activity_score': 0,
                'post_count': 0,
                'posts_data': [],
                'timestamp': datetime.now().isoformat()
            }
    
    @staticmethod
    def _basic_analysis(html_content: str) -> Dict[str, Any]:
        """Analyse de base (code existant adapté)"""
        activity_patterns = [
            r'feed-shared-update-v2',
            r'feed-shared-actor',
            r'update-components-text',
            r'posted\s+this',
            r'shared\s+this',
            r'published\s+on',
            r'activity-actor',
            r'share-update-card'
        ]
        
        activity_score = 0
        for pattern in activity_patterns:
            matches = len(re.findall(pattern, html_content, re.IGNORECASE))
            activity_score += matches * 3
        
        return {'activity_score': activity_score}
    
    @staticmethod
    def _generate_posts_hash(posts_data: List[PostData]) -> str:
        """Génère un hash basé sur les posts récents"""
        if not posts_data:
            return f"no_posts_{int(time.time())}"
        
        # Concaténer les titres et descriptions des posts
        combined_content = ""
        for post in posts_data:
            combined_content += f"{post.post_title}{post.post_description}"
        
        return hashlib.sha256(combined_content.encode('utf-8')).hexdigest()[:20]


class LinkedInMonitor:
    """Agent principal de monitoring LinkedIn - Version améliorée"""
    
    def __init__(self, csv_file: str, email_config: Dict[str, str]):
        self.csv_file = csv_file
        self.notifier = GroupedEmailNotifier(
            email_config['sender_email'],
            email_config['sender_password'],
            email_config['recipient_email']
        )
        
        # Configuration de session HTTP
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Collecteur pour tous les nouveaux posts
        self.all_new_posts: List[PostData] = []
        
        # Statistiques
        self.stats = {
            'total': 0,
            'success': 0,
            'changes': 0,
            'new_posts': 0,
            'errors': 0
        }
    
    def load_profiles(self) -> List[ProfileData]:
        """Chargement des profils depuis CSV (code existant)"""
        try:
            if not os.path.exists(self.csv_file):
                print(f"❌ Fichier CSV non trouvé: {self.csv_file}")
                return self._create_default_profiles()
            
            profiles = []
            
            for encoding in ['utf-8-sig', 'utf-8', 'iso-8859-1']:
                try:
                    with open(self.csv_file, 'r', encoding=encoding, newline='') as file:
                        reader = csv.DictReader(file)
                        for i, row in enumerate(reader, 1):
                            profile = self._parse_row(row, i)
                            if profile:
                                profiles.append(profile)
                    
                    print(f"✅ {len(profiles)} profils chargés (encodage: {encoding})")
                    return profiles
                    
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    print(f"❌ Erreur lecture {encoding}: {e}")
                    continue
            
            print("❌ Impossible de lire le fichier CSV")
            return self._create_default_profiles()
            
        except Exception as e:
            print(f"❌ Erreur chargement: {e}")
            return self._create_default_profiles()
    
    def _parse_row(self, row: Dict[str, Any], line_num: int) -> Optional[ProfileData]:
        """Parse une ligne CSV en ProfileData (code existant)"""
        try:
            url = str(row.get('URL', '')).strip()
            name = str(row.get('Name', '')).strip()
            last_id = str(row.get('Last_Post_ID', '')).strip()
            error_count = int(row.get('Error_Count', 0) or 0)
            
            if not url or not name:
                print(f"⚠️ Ligne {line_num}: URL ou nom manquant")
                return None
            
            if not self._is_valid_linkedin_url(url):
                print(f"⚠️ Ligne {line_num}: URL LinkedIn invalide")
                return None
            
            profile = ProfileData(url, name, last_id, error_count)
            print(f"✅ Ligne {line_num}: {name}")
            return profile
            
        except Exception as e:
            print(f"❌ Erreur ligne {line_num}: {e}")
            return None
    
    def _is_valid_linkedin_url(self, url: str) -> bool:
        """Validation d'URL LinkedIn (code existant)"""
        patterns = [
            r'^https://www\.linkedin\.com/company/[^/]+/?(?:posts/?)?$',
            r'^https://www\.linkedin\.com/in/[^/]+/?$'
        ]
        return any(re.match(pattern, url) for pattern in patterns)
    
    def _create_default_profiles(self) -> List[ProfileData]:
        """Création de profils par défaut (code existant)"""
        defaults = [
            ProfileData("https://www.linkedin.com/company/microsoft/posts/", "Microsoft"),
            ProfileData("https://www.linkedin.com/company/tesla-motors/posts/", "Tesla"), 
            ProfileData("https://www.linkedin.com/company/google/posts/", "Google")
        ]
        print("📝 Création de profils par défaut")
        self.save_profiles(defaults)
        return defaults
    
    def check_profile(self, profile: ProfileData) -> Optional[Dict[str, Any]]:
        """Vérification d'un profil avec extraction des posts détaillés"""
        try:
            print(f"🔍 Vérification: {profile.name}")
            
            # Optimisation de l'URL
            check_url = self._optimize_url(profile.url)
            
            # Requête HTTP
            response = self._make_request(check_url)
            if not response or response.status_code != 200:
                print(f"❌ Erreur HTTP: {response.status_code if response else 'Aucune réponse'}")
                profile.error_count += 1
                return None
            
            # Analyse détaillée avec extraction des posts
            analysis = ContentAnalyzer.analyze_content_with_posts(
                response.text, profile.url, profile.name
            )
            
            print(f"📊 Score: {analysis['activity_score']}, Posts: {analysis['post_count']}, Hash: {analysis['content_hash'][:12]}...")
            
            profile.error_count = 0  # Reset en cas de succès
            return analysis
            
        except Exception as e:
            print(f"❌ Erreur {profile.name}: {e}")
            profile.error_count += 1
            return None
    
    def _optimize_url(self, url: str) -> str:
        """Optimise l'URL pour récupérer les posts (code existant)"""
        if '/company/' in url and not url.endswith('/posts/'):
            if not url.endswith('/'):
                url += '/'
            if not url.endswith('posts/'):
                url += 'posts/'
        return url
    
    def _make_request(self, url: str) -> Optional[requests.Response]:
        """Requête HTTP avec retry (code existant)"""
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=30)
                if response.status_code == 429:  # Rate limiting
                    wait_time = 60 + (attempt * 30)
                    print(f"⏰ Rate limit, attente {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                return response
            except requests.exceptions.RequestException as e:
                print(f"❌ Tentative {attempt + 1}/3: {e}")
                if attempt < 2:
                    time.sleep(10)
        return None
    
    def save_profiles(self, profiles: List[ProfileData]) -> bool:
        """Sauvegarde des profils en CSV (code existant)"""
        try:
            fieldnames = ['URL', 'Name', 'Last_Post_ID', 'Error_Count']
            
            with open(self.csv_file, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for profile in profiles:
                    writer.writerow(profile.to_dict())
            
            print("💾 Profils sauvegardés")
            return True
            
        except Exception as e:
            print(f"❌ Erreur sauvegarde: {e}")
            return False
    
    def run_monitoring(self) -> bool:
        """Cycle principal de monitoring avec notification groupée"""
        try:
            print("=" * 80)
            print(f"🚀 LINKEDIN MONITORING AMÉLIORÉ - {datetime.now()}")
            print("=" * 80)
            
            # Chargement des profils
            profiles = self.load_profiles()
            if not profiles:
                print("❌ Aucun profil à surveiller")
                return False
            
            self.stats['total'] = len(profiles)
            changes_made = False
            self.all_new_posts = []  # Reset du collecteur
            
            # Traitement de chaque profil
            for i, profile in enumerate(profiles):
                try:
                    print(f"\n--- {i+1}/{len(profiles)}: {profile.name} ---")
                    print(f"🔗 URL: {profile.url}")
                    print(f"🆔 Dernier hash: {profile.last_post_id[:15]}..." if profile.last_post_id else "🆔 Première vérification")
                    
                    # Vérification avec analyse détaillée
                    analysis = self.check_profile(profile)
                    
                    if analysis:
                        self.stats['success'] += 1
                        current_hash = analysis['content_hash']
                        
                        # Détection de changement
                        if profile.last_post_id != current_hash:
                            print(f"🆕 CHANGEMENT DÉTECTÉ!")
                            self.stats['changes'] += 1
                            changes_made = True
                            
                            # Ajout des nouveaux posts au collecteur
                            new_posts = analysis.get('posts_data', [])
                            if new_posts:
                                self.all_new_posts.extend(new_posts)
                                self.stats['new_posts'] += len(new_posts)
                                print(f"📝 {len(new_posts)} nouveau{'x' if len(new_posts) > 1 else ''} post{'s' if len(new_posts) > 1 else ''} collecté{'s' if len(new_posts) > 1 else ''}")
                            
                            # Mise à jour du hash
                            profile.last_post_id = current_hash
                        else:
                            print("⚪ Aucun changement")
                    else:
                        self.stats['errors'] += 1
                    
                    # Pause entre les profils
                    if i < len(profiles) - 1:
                        pause = 15 + (i % 3) * 5  # 15-25 secondes
                        print(f"⏳ Pause {pause}s...")
                        time.sleep(pause)
                
                except Exception as e:
                    print(f"❌ Erreur traitement {profile.name}: {e}")
                    self.stats['errors'] += 1
            
            # Sauvegarde si changements
            if changes_made:
                self.save_profiles(profiles)
            
            # Envoi de la notification groupée
            if self.all_new_posts:
                print(f"\n📧 Envoi notification groupée: {len(self.all_new_posts)} posts")
                if self.notifier.send_grouped_notification(self.all_new_posts):
                    print("✅ Notification groupée envoyée avec succès")
                else:
                    print("❌ Échec notification groupée")
            else:
                print("\n📧 Aucun nouveau post à notifier")
            
            # Rapport final
            self._print_report()
            
            return self.stats['success'] > 0
            
        except Exception as e:
            print(f"💥 ERREUR CRITIQUE: {e}")
            traceback.print_exc()
            return False
    
    def _print_report(self):
        """Rapport final amélioré"""
        print("\n" + "=" * 80)
        print("📊 RAPPORT FINAL DÉTAILLÉ")
        print("=" * 80)
        print(f"📋 Profils traités: {self.stats['success']}/{self.stats['total']}")
        print(f"🆕 Changements détectés: {self.stats['changes']}")
        print(f"📝 Nouveaux posts collectés: {self.stats['new_posts']}")
        print(f"📧 Notification groupée: {'✅ Envoyée' if self.all_new_posts else '⚪ Aucune'}")
        print(f"❌ Erreurs: {self.stats['errors']}")
        
        success_rate = (self.stats['success'] / self.stats['total']) * 100 if self.stats['total'] > 0 else 0
        print(f"📈 Taux de succès: {success_rate:.1f}%")
        
        if self.all_new_posts:
            print(f"\n🎯 DÉTAILS DES NOUVEAUX POSTS:")
            profiles_summary = {}
            for post in self.all_new_posts:
                if post.profile_name not in profiles_summary:
                    profiles_summary[post.profile_name] = 0
                profiles_summary[post.profile_name] += 1
            
            for profile, count in profiles_summary.items():
                print(f"   • {profile}: {count} post{'s' if count > 1 else ''}")
        
        print("=" * 80)


def validate_environment() -> Dict[str, str]:
    """Validation de l'environnement (code existant)"""
    print("🔧 Validation de l'environnement...")
    
    required_vars = {
        'GMAIL_EMAIL': 'sender_email',
        'GMAIL_APP_PASSWORD': 'sender_password', 
        'RECIPIENT_EMAIL': 'recipient_email'
    }
    
    config = {}
    missing = []
    
    for env_var, config_key in required_vars.items():
        value = os.getenv(env_var, '').strip()
        if value:
            config[config_key] = value
            display_value = value[:3] + "*" * (len(value)-6) + value[-3:] if len(value) > 6 else "***"
            print(f"✅ {env_var}: {display_value}")
        else:
            missing.append(env_var)
            print(f"❌ {env_var}: MANQUANT")
    
    if missing:
        print(f"\n💥 Variables manquantes: {', '.join(missing)}")
        print("💡 Configurez dans GitHub Secrets:")
        print("   Repository → Settings → Secrets and variables → Actions")
        raise ValueError(f"Configuration incomplète: {missing}")
    
    print("✅ Configuration validée")
    return config


def main():
    """Point d'entrée principal"""
    try:
        print("🎯" + "=" * 78 + "🎯")
        print("🤖 LINKEDIN MONITORING AGENT - VERSION AMÉLIORÉE")
        print("🔥 Nouvelles fonctionnalités:")
        print("   • 📧 Notifications groupées intelligentes") 
        print("   • 🔗 Extraction directe des liens de posts")
        print("   • 📝 Descriptions automatiques des contenus")
        print("   • 🎨 Interface email moderne et responsive")
        print("🎯" + "=" * 78 + "🎯")
        
        # Validation
        email_config = validate_environment()
        
        # Monitoring amélioré
        monitor = LinkedInMonitor("linkedin_urls.csv", email_config)
        success = monitor.run_monitoring()
        
        # Résultat
        if success:
            print("🎉 MONITORING TERMINÉ AVEC SUCCÈS")
            if monitor.all_new_posts:
                print(f"🚀 {len(monitor.all_new_posts)} nouveaux posts détectés et notifiés")
            sys.exit(0)
        else:
            print("💥 ÉCHEC DU MONITORING")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n⏹️ Arrêt demandé")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 ERREUR FATALE: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
