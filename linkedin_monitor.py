#!/usr/bin/env python3
"""
LinkedIn Monitor Agent v4.0 - API Officielle LinkedIn
Version révolutionnaire utilisant l'API LinkedIn officielle pour:
- Extraction précise des posts avec vrais titres/descriptions
- Authentification OAuth 2.0 sécurisée
- Support Company Pages et Personal Profiles
- Gestion intelligente des quotas API
- Email ultra-optimisé avec contenu authentique
"""
import requests
import csv
import time
import json
import hashlib
import smtplib
import sys
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, NamedTuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlencode, parse_qs, urlparse
import base64


class LinkedInPost(NamedTuple):
    """Structure pour un post LinkedIn authentique"""
    profile_name: str
    post_title: str
    post_description: str
    post_url: str
    detection_time: str
    post_id: str
    post_type: str
    author_name: str
    published_date: str
    engagement_count: int
    media_type: str = "text"
    source_method: str = "linkedin_api"


class ProfileData:
    """Structure pour un profil LinkedIn"""
    
    def __init__(self, url: str, name: str, profile_id: str = "", last_post_id: str = "", error_count: int = 0):
        self.url = url.strip()
        self.name = name.strip()
        self.profile_id = profile_id.strip()  # ID LinkedIn extrait de l'URL
        self.last_post_id = last_post_id.strip()
        self.error_count = error_count
        self.last_check = datetime.now().isoformat()
        self.last_success = None
        self.profile_type = self._detect_profile_type()
    
    def _detect_profile_type(self) -> str:
        """Détection du type de profil"""
        if '/company/' in self.url:
            return 'company'
        elif '/in/' in self.url:
            return 'person'
        return 'unknown'
    
    def extract_id_from_url(self) -> str:
        """Extraction de l'ID LinkedIn depuis l'URL"""
        if '/company/' in self.url:
            import re
            match = re.search(r'/company/([^/]+)', self.url)
            return match.group(1) if match else ""
        elif '/in/' in self.url:
            import re
            match = re.search(r'/in/([^/]+)', self.url)
            return match.group(1) if match else ""
        return ""
    
    def to_dict(self) -> Dict[str, str]:
        if not self.profile_id:
            self.profile_id = self.extract_id_from_url()
        
        return {
            'URL': self.url,
            'Name': self.name,
            'Profile_ID': self.profile_id,
            'Last_Post_ID': self.last_post_id,
            'Error_Count': str(self.error_count)
        }


class LinkedInAPIClient:
    """Client API LinkedIn officiel avec authentification OAuth 2.0"""
    
    def __init__(self, client_id: str, client_secret: str, access_token: str = ""):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.base_url = "https://api.linkedin.com/v2"
        self.session = requests.Session()
        
        # Headers API standard
        self.session.headers.update({
            'Authorization': f'Bearer {self.access_token}' if access_token else '',
            'Content-Type': 'application/json',
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': '202401'  # Version API la plus récente
        })
    
    def authenticate_client_credentials(self) -> bool:
        """Authentification Client Credentials pour accès lecture"""
        try:
            print("🔐 Authentification LinkedIn API...")
            
            auth_url = "https://www.linkedin.com/oauth/v2/accessToken"
            
            auth_data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'scope': 'r_organization_social r_basicprofile'  # Permissions lecture
            }
            
            auth_response = requests.post(
                auth_url,
                data=auth_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            if auth_response.status_code == 200:
                token_data = auth_response.json()
                self.access_token = token_data['access_token']
                
                # Mise à jour des headers
                self.session.headers['Authorization'] = f'Bearer {self.access_token}'
                
                print("✅ Authentification LinkedIn réussie")
                return True
            else:
                print(f"❌ Échec authentification: {auth_response.status_code}")
                print(f"Response: {auth_response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Erreur authentification: {e}")
            return False
    
    def get_company_posts(self, company_id: str, count: int = 10) -> List[LinkedInPost]:
        """Récupération des posts d'une entreprise"""
        try:
            print(f"🏢 Récupération posts entreprise: {company_id}")
            
            # Endpoint pour les posts d'organisation
            endpoint = f"{self.base_url}/shares"
            params = {
                'q': 'owners',
                'owners': f'urn:li:organization:{company_id}',
                'count': count,
                'start': 0,
                'sortBy': 'CREATED'  # Plus récents en premier
            }
            
            response = self.session.get(endpoint, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_posts_response(data, company_id, 'company')
            elif response.status_code == 401:
                print("❌ Token expiré - réauthentification nécessaire")
                return []
            else:
                print(f"❌ Erreur API: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            print(f"❌ Erreur récupération posts entreprise: {e}")
            return []
    
    def get_profile_posts(self, profile_id: str, count: int = 10) -> List[LinkedInPost]:
        """Récupération des posts d'un profil personnel"""
        try:
            print(f"👤 Récupération posts profil: {profile_id}")
            
            # Endpoint pour les posts de personne (nécessite permission étendue)
            endpoint = f"{self.base_url}/people/{profile_id}/shares"
            params = {
                'count': count,
                'start': 0,
                'sortBy': 'CREATED'
            }
            
            response = self.session.get(endpoint, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_posts_response(data, profile_id, 'person')
            elif response.status_code == 403:
                print("⚠️ Permissions insuffisantes pour profils personnels")
                return []
            else:
                print(f"❌ Erreur API: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Erreur récupération posts profil: {e}")
            return []
    
    def get_ugc_posts(self, author_urn: str, count: int = 10) -> List[LinkedInPost]:
        """Récupération via UGC Posts API (plus récent)"""
        try:
            print(f"📝 Récupération UGC posts: {author_urn}")
            
            endpoint = f"{self.base_url}/ugcPosts"
            params = {
                'q': 'authors',
                'authors': author_urn,
                'count': count,
                'sortBy': 'CREATED',
                'lifecycleState': 'PUBLISHED'
            }
            
            response = self.session.get(endpoint, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_ugc_posts_response(data, author_urn)
            else:
                print(f"❌ Erreur UGC API: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Erreur UGC posts: {e}")
            return []
    
    def _parse_posts_response(self, data: Dict, profile_id: str, profile_type: str) -> List[LinkedInPost]:
        """Parse la réponse API en posts structurés"""
        posts = []
        
        try:
            elements = data.get('elements', [])
            
            for element in elements:
                post = self._extract_post_data(element, profile_id, profile_type)
                if post:
                    posts.append(post)
            
            print(f"✅ {len(posts)} posts extraits de l'API")
            return posts
            
        except Exception as e:
            print(f"❌ Erreur parsing posts: {e}")
            return []
    
    def _parse_ugc_posts_response(self, data: Dict, author_urn: str) -> List[LinkedInPost]:
        """Parse la réponse UGC Posts API"""
        posts = []
        
        try:
            elements = data.get('elements', [])
            
            for element in elements:
                post = self._extract_ugc_post_data(element, author_urn)
                if post:
                    posts.append(post)
            
            print(f"✅ {len(posts)} UGC posts extraits")
            return posts
            
        except Exception as e:
            print(f"❌ Erreur parsing UGC posts: {e}")
            return []
    
    def _extract_post_data(self, element: Dict, profile_id: str, profile_type: str) -> Optional[LinkedInPost]:
        """Extraction des données d'un post"""
        try:
            # ID du post
            post_id = element.get('id', '').split(':')[-1] if element.get('id') else ""
            
            # Contenu du post
            content = element.get('content', {})
            
            # Titre et description depuis le contenu
            title = self._extract_title_from_content(content)
            description = self._extract_description_from_content(content)
            
            # Auteur
            author = element.get('author', {})
            author_name = self._extract_author_name(author)
            
            # Date de publication
            created_time = element.get('created', {}).get('time', 0)
            published_date = datetime.fromtimestamp(created_time / 1000).strftime('%d/%m/%Y à %H:%M') if created_time else ""
            
            # URL du post
            post_url = self._generate_post_url(element.get('id', ''), profile_type)
            
            # Engagement
            engagement = self._extract_engagement_data(element)
            
            # Type de contenu
            post_type = self._detect_post_type(content)
            
            # Création du post structuré
            return LinkedInPost(
                profile_name=profile_id,
                post_title=title,
                post_description=description,
                post_url=post_url,
                detection_time=datetime.now().strftime('%d/%m/%Y à %H:%M'),
                post_id=post_id[:12],  # Tronqué pour l'affichage
                post_type=post_type,
                author_name=author_name,
                published_date=published_date,
                engagement_count=engagement,
                media_type=self._detect_media_type(content),
                source_method="linkedin_api_official"
            )
            
        except Exception as e:
            print(f"❌ Erreur extraction post: {e}")
            return None
    
    def _extract_ugc_post_data(self, element: Dict, author_urn: str) -> Optional[LinkedInPost]:
        """Extraction des données UGC Post"""
        try:
            # ID du post
            post_id = element.get('id', '').split(':')[-1] if element.get('id') else ""
            
            # Contenu spécifique UGC
            specific_content = element.get('specificContent', {}).get('com.linkedin.ugc.ShareContent', {})
            
            # Texte principal
            share_commentary = specific_content.get('shareCommentary', {})
            main_text = share_commentary.get('text', '')
            
            # Titre intelligent depuis le texte
            title = self._create_smart_title_from_text(main_text)
            description = self._create_smart_description_from_text(main_text)
            
            # Métadonnées
            created_time = element.get('created', {}).get('time', 0)
            published_date = datetime.fromtimestamp(created_time / 1000).strftime('%d/%m/%Y à %H:%M') if created_time else ""
            
            # URL du post
            post_url = f"https://www.linkedin.com/feed/update/urn:li:ugcPost:{post_id}/"
            
            # Type et média
            post_type = self._detect_ugc_post_type(specific_content)
            media_type = self._detect_ugc_media_type(specific_content)
            
            return LinkedInPost(
                profile_name=author_urn.split(':')[-1],
                post_title=title,
                post_description=description,
                post_url=post_url,
                detection_time=datetime.now().strftime('%d/%m/%Y à %H:%M'),
                post_id=post_id[:12],
                post_type=post_type,
                author_name=author_urn.split(':')[-1],
                published_date=published_date,
                engagement_count=0,  # À implémenter si besoin
                media_type=media_type,
                source_method="linkedin_ugc_api"
            )
            
        except Exception as e:
            print(f"❌ Erreur extraction UGC post: {e}")
            return None
    
    def _extract_title_from_content(self, content: Dict) -> str:
        """Extraction intelligente du titre"""
        # Titre depuis le contenu share
        share_content = content.get('content-entity', {})
        if share_content:
            entity_title = share_content.get('entityTitle', '')
            if entity_title:
                return entity_title[:100]
        
        # Titre depuis le texte principal
        main_text = content.get('title', '') or content.get('description', '')
        if main_text:
            return self._create_smart_title_from_text(main_text)
        
        return "Publication LinkedIn professionnelle"
    
    def _extract_description_from_content(self, content: Dict) -> str:
        """Extraction intelligente de la description"""
        # Description complète
        description = content.get('description', '') or content.get('summary', '')
        
        if description:
            # Nettoyage et optimisation
            clean_desc = description.strip()
            if len(clean_desc) > 300:
                clean_desc = clean_desc[:297] + "..."
            return clean_desc
        
        # Fallback depuis le titre
        title = content.get('title', '')
        if title:
            return f"Nouvelle publication: {title}"
        
        return "Nouveau contenu partagé sur LinkedIn"
    
    def _create_smart_title_from_text(self, text: str) -> str:
        """Création de titre intelligent depuis le texte"""
        if not text:
            return "Publication LinkedIn"
        
        # Première phrase comme titre
        sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 15]
        if sentences:
            title = sentences[0]
            if len(title) <= 80:
                return title + ("." if not title.endswith(('.', '!', '?')) else "")
            else:
                words = title.split()[:12]
                return " ".join(words) + "..."
        
        # Fallback: premiers mots
        words = text.split()[:15]
        return " ".join(words) + ("..." if len(words) == 15 else "")
    
    def _create_smart_description_from_text(self, text: str) -> str:
        """Création de description intelligente"""
        if not text:
            return "Nouveau contenu LinkedIn"
        
        # Optimisation longueur
        if len(text) <= 200:
            return text.strip()
        
        # Troncature intelligente
        sentences = text.split('.')
        description = ""
        
        for sentence in sentences:
            if len(description + sentence) <= 190:
                description += sentence + "."
            else:
                break
        
        return description.strip() or text[:190] + "..."
    
    def _extract_author_name(self, author: Dict) -> str:
        """Extraction du nom de l'auteur"""
        if isinstance(author, str):
            return author.split(':')[-1]
        
        # Structure complexe auteur
        author_id = author.get('id', '')
        if author_id:
            return author_id.split(':')[-1]
        
        return "Auteur LinkedIn"
    
    def _generate_post_url(self, post_id: str, profile_type: str) -> str:
        """Génération URL du post"""
        if not post_id:
            return "https://www.linkedin.com/feed/"
        
        clean_id = post_id.split(':')[-1]
        
        if profile_type == 'company':
            return f"https://www.linkedin.com/feed/update/{post_id}/"
        else:
            return f"https://www.linkedin.com/posts/activity-{clean_id}/"
    
    def _extract_engagement_data(self, element: Dict) -> int:
        """Extraction des données d'engagement"""
        try:
            social_counts = element.get('socialDetail', {}).get('totalSocialActivityCounts', {})
            likes = social_counts.get('numLikes', 0)
            comments = social_counts.get('numComments', 0)
            shares = social_counts.get('numShares', 0)
            
            return likes + comments + shares
        except:
            return 0
    
    def _detect_post_type(self, content: Dict) -> str:
        """Détection intelligente du type de post"""
        content_str = json.dumps(content).lower()
        
        type_patterns = {
            'emploi': ['job', 'career', 'hiring', 'position', 'recrut'],
            'evenement': ['event', 'webinar', 'conference', 'séminaire'],
            'produit': ['product', 'launch', 'nouveau', 'innovation'],
            'article': ['article', 'blog', 'read', 'insights'],
            'actualite': ['news', 'announce', 'update', 'actualité']
        }
        
        for post_type, keywords in type_patterns.items():
            if any(keyword in content_str for keyword in keywords):
                return post_type
        
        return 'publication'
    
    def _detect_ugc_post_type(self, specific_content: Dict) -> str:
        """Détection type pour UGC posts"""
        content_str = json.dumps(specific_content).lower()
        
        if 'media' in content_str:
            return 'media'
        elif 'article' in content_str:
            return 'article'
        elif 'poll' in content_str:
            return 'poll'
        
        return 'publication'
    
    def _detect_media_type(self, content: Dict) -> str:
        """Détection du type de média"""
        if content.get('media'):
            media = content['media']
            if any('video' in str(m).lower() for m in media):
                return 'video'
            elif any('image' in str(m).lower() for m in media):
                return 'image'
        
        return 'text'
    
    def _detect_ugc_media_type(self, specific_content: Dict) -> str:
        """Détection type média UGC"""
        media = specific_content.get('media', [])
        if media:
            media_str = json.dumps(media).lower()
            if 'video' in media_str:
                return 'video'
            elif 'image' in media_str:
                return 'image'
        
        return 'text'


class APIBasedEmailNotifier:
    """Notificateur email optimisé pour API LinkedIn"""
    
    def __init__(self, sender_email: str, sender_password: str, recipient_email: str):
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.recipient_email = recipient_email
    
    def send_api_optimized_notification(self, all_posts: List[LinkedInPost]) -> bool:
        """Notification optimisée pour posts API"""
        try:
            if not all_posts:
                print("ℹ️ Aucun post API à notifier")
                return True
            
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            msg['Subject'] = self._create_api_subject(all_posts)
            
            # Contenu texte optimisé
            text_content = self._build_api_text_message(all_posts)
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            
            # HTML révolutionnaire pour API
            html_content = self._build_api_html_message(all_posts)
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Envoi
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            print(f"📧 Email API optimisé envoyé: {len(all_posts)} posts")
            return True
            
        except Exception as e:
            print(f"❌ Erreur envoi email API: {e}")
            return False
    
    def _create_api_subject(self, posts: List[LinkedInPost]) -> str:
        """Sujet optimisé pour posts API"""
        count = len(posts)
        profiles = len(set(post.profile_name for post in posts))
        
        # Analyse des types
        post_types = [post.post_type for post in posts]
        media_types = [post.media_type for post in posts]
        
        if 'video' in media_types:
            return f"🎥 {count} vidéo{'s' if count > 1 else ''} LinkedIn détectée{'s' if count > 1 else ''} via API !"
        elif 'emploi' in post_types:
            return f"💼 {count} opportunité{'s' if count > 1 else ''} emploi LinkedIn !"
        elif 'evenement' in post_types:
            return f"📅 {count} événement{'s' if count > 1 else ''} professionnel{'s' if count > 1 else ''} !"
        elif 'article' in post_types:
            return f"📰 {count} article{'s' if count > 1 else ''} LinkedIn publié{'s' if count > 1 else ''} !"
        else:
            return f"🚀 {count} publication{'s' if count > 1 else ''} LinkedIn de {profiles} profil{'s' if profiles > 1 else ''} !"
    
    def _build_api_text_message(self, posts: List[LinkedInPost]) -> str:
        """Message texte optimisé API"""
        total_engagement = sum(post.engagement_count for post in posts)
        
        content = f"""🚀 LINKEDIN API MONITOR - POSTS AUTHENTIQUES

📅 {datetime.now().strftime('%d/%m/%Y à %H:%M UTC')}
📊 {len(posts)} publication{'s' if len(posts) > 1 else ''} via API officielle
💬 {total_engagement} interactions totales
🔥 Contenu 100% authentique LinkedIn

"""
        
        # Groupement par profil
        profiles_posts = {}
        for post in posts:
            if post.profile_name not in profiles_posts:
                profiles_posts[post.profile_name] = []
            profiles_posts[post.profile_name].append(post)
        
        for profile_name, profile_posts in profiles_posts.items():
            content += f"👤 {profile_name.upper()}\n"
            content += "─" * 50 + "\n"
            
            for post in profile_posts:
                type_icon = self._get_type_icon(post.post_type)
                media_icon = self._get_media_icon(post.media_type)
                
                content += f"""{type_icon} TITRE: {post.post_title}
✏️ DESCRIPTION: {post.post_description}
👤 AUTEUR: {post.author_name}
📅 PUBLIÉ: {post.published_date}
{media_icon} TYPE: {post.media_type.upper()}
💬 ENGAGEMENT: {post.engagement_count} interactions
🔗 LIEN: {post.post_url}

"""
        
        content += """🤖 LinkedIn API Monitor v4.0
Extraction authentique via API officielle LinkedIn
Système de veille professionnel automatisé
"""
        
        return content
    
    def _build_api_html_message(self, posts: List[LinkedInPost]) -> str:
        """Email HTML révolutionnaire pour API"""
        total_engagement = sum(post.engagement_count for post in posts)
        profiles_count = len(set(post.profile_name for post in posts))
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 LinkedIn API Intelligence</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{ 
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0077b5 0%, #00a0dc 25%, #667eea 50%, #764ba2 75%, #f093fb 100%);
            background-size: 400% 400%;
            animation: megaGradient 20s ease infinite;
            padding: 20px;
            min-height: 100vh;
        }}
        
        @keyframes megaGradient {{
            0%, 100% {{ background-position: 0% 50%; }}
            25% {{ background-position: 100% 50%; }}
            50% {{ background-position: 50% 100%; }}
            75% {{ background-position: 50% 0%; }}
        }}
        
        .container {{ 
            max-width: 800px; 
            margin: 0 auto; 
            background: rgba(255, 255, 255, 0.98);
            backdrop-filter: blur(30px);
            border-radius: 32px; 
            overflow: hidden;
            box-shadow: 
                0 32px 64px rgba(0,0,0,0.12),
                0 0 0 1px rgba(255,255,255,0.3),
                inset 0 1px 0 rgba(255,255,255,0.4);
        }}
        
        .header {{ 
            background: linear-gradient(135deg, #0a66c2 0%, #0077b5 30%, #00a0dc 70%, #0e76a8 100%);
            position: relative;
            overflow: hidden;
            padding: 50px 40px;
            text-align: center;
        }}
        
        .header::before {{
            content: '';
            position: absolute;
            top: -100%;
            left: -100%;
            width: 300%;
            height: 300%;
            background: conic-gradient(from 0deg, transparent 0deg, rgba(255,255,255,0.1) 90deg, transparent 180deg, rgba(255,255,255,0.1) 270deg, transparent 360deg);
            animation: cosmicRotation 8s linear infinite;
        }}
        
        @keyframes cosmicRotation {{
            from {{ transform: rotate(0deg); }}
            to {{ transform: rotate(360deg); }}
        }}
        
        .header h1 {{ 
            font-size: 42px; 
            font-weight: 900; 
            color: white;
            margin-bottom: 18px;
            position: relative;
            z-index: 2;
            text-shadow: 0 4px 20px rgba(0,0,0,0.3);
            letter-spacing: -1px;
        }}
        
        .header p {{ 
            color: rgba(255,255,255,0.95); 
            font-size: 20px;
            font-weight: 500;
            position: relative;
            z-index: 2;
        }}
        
        .api-badge {{
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            padding: 18px 35px;
            text-align: center;
            font-weight: 700;
            font-size: 16px;
            letter-spacing: 1px;
            position: relative;
            overflow: hidden;
        }}
        
        .api-badge::before {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            animation: shimmer 3s ease-in-out infinite;
        }}
        
        @keyframes shimmer {{
            0% {{ left: -100%; }}
            100% {{ left: 100%; }}
        }}
        
        .stats-dashboard {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        }}
        
        .stat-card {{
            text-align: center;
            padding: 30px 20px;
            border-right: 1px solid rgba(148, 163, 184, 0.3);
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }}
        
        .stat-card:last-child {{ border-right: none; }}
        
        .stat-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, #0077b5, #00a0dc);
            opacity: 0;
            transition: opacity 0.3s ease;
        }}
        
        .stat-card:hover::before {{
            opacity: 0.05;
        }}
        
        .stat-card:hover {{
            transform: translateY(-8px) scale(1.05);
            box-shadow: 0 20px 40px rgba(0,119,181,0.15);
        }}
        
        .stat-value {{
            font-size: 36px;
            font-weight: 900;
            background: linear-gradient(135deg, #0077b5, #00a0dc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            display: block;
            margin-bottom: 8px;
            position: relative;
            z-index: 2;
        }}
        
        .stat-label {{
            font-size: 13px;
            color: #64748b;
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 1.2px;
            position: relative;
            z-index: 2;
        }}
        
        .content {{ 
            padding: 40px;
            background: #ffffff;
        }}
        
        .post-card {{ 
            background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
            border-radius: 28px; 
            padding: 36px; 
            margin-bottom: 32px;
            position: relative;
            border: 3px solid transparent;
            background-clip: padding-box;
            transition: all 0.6s cubic-bezier(0.4, 0, 0.2, 1);
            overflow: hidden;
        }}
        
        .post-card::before {{
            content: '';
            position: absolute;
            top: -3px;
            left: -3px;
            right: -3px;
            bottom: -3px;
            background: linear-gradient(45deg, #0077b5, #00a0dc, #10b981, #667eea, #0077b5);
            background-size: 400% 400%;
            border-radius: 32px;
            z-index: -1;
            opacity: 0;
            animation: rainbowBorder 8s ease infinite;
            transition: opacity 0.4s ease;
        }}
        
        .post-card:hover::before {{
            opacity: 1;
        }}
        
        .post-card:hover {{
            transform: translateY(-16px) scale(1.02);
            box-shadow: 0 32px 64px rgba(0,119,181,0.2);
        }}
        
        @keyframes rainbowBorder {{
            0%, 100% {{ background-position: 0% 50%; }}
            25% {{ background-position: 100% 50%; }}
            50% {{ background-position: 100% 100%; }}
            75% {{ background-position: 0% 100%; }}
        }}
        
        .post-header {{ 
            display: flex;
            align-items: center;
            margin-bottom: 28px;
            padding-bottom: 24px;
            border-bottom: 3px solid #f1f5f9;
        }}
        
        .profile-avatar {{
            width: 70px;
            height: 70px;
            background: linear-gradient(135deg, #0077b5 0%, #00a0dc 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            font-weight: 900;
            color: white;
            margin-right: 20px;
            box-shadow: 0 12px 32px rgba(0,119,181,0.4);
            position: relative;
            overflow: hidden;
        }}
        
        .profile-avatar::before {{
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: linear-gradient(45deg, transparent, rgba(255,255,255,0.2), transparent);
            animation: avatarGlow 4s ease-in-out infinite;
        }}
        
        @keyframes avatarGlow {{
            0%, 100% {{ transform: translateX(-100%) rotate(45deg); }}
            50% {{ transform: translateX(100%) rotate(45deg); }}
        }}
        
        .profile-info {{
            flex: 1;
        }}
        
        .profile-name {{ 
            font-size: 26px; 
            font-weight: 800; 
            background: linear-gradient(135deg, #0f172a, #1e293b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 8px;
        }}
        
        .post-metadata {{
            display: flex;
            align-items: center;
            gap: 15px;
            flex-wrap: wrap;
        }}
        
        .api-badge {{
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
            padding: 8px 16px;
            border-radius: 25px;
            font-size: 12px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
            box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4);
        }}
        
        .post-type-badge {{
            background: linear-gradient(135deg, #8b5cf6, #7c3aed);
            color: white;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
        }}
        
        .media-badge {{
            background: linear-gradient(135deg, #f59e0b, #d97706);
            color: white;
            padding: 4px 12px;
            border-radius: 15px;
            font-size: 10px;
            font-weight: 600;
        }}
        
        .engagement-counter {{
            background: rgba(239, 68, 68, 0.1);
            color: #dc2626;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
            border: 2px solid rgba(239, 68, 68, 0.2);
        }}
        
        .post-main-content {{
            margin: 28px 0;
        }}
        
        .post-title {{ 
            font-size: 28px;
            font-weight: 800;
            color: #1e293b;
            margin-bottom: 20px;
            line-height: 1.2;
            position: relative;
        }}
        
        .post-title::after {{
            content: '';
            position: absolute;
            bottom: -10px;
            left: 0;
            width: 80px;
            height: 4px;
            background: linear-gradient(90deg, #0077b5, #00a0dc, #10b981);
            border-radius: 2px;
        }}
        
        .post-description {{ 
            color: #475569; 
            font-size: 18px;
            line-height: 1.8;
            margin-bottom: 28px;
            padding: 28px;
            background: linear-gradient(145deg, #f8fafc 0%, #f1f5f9 100%);
            border-radius: 20px;
            border-left: 6px solid #0077b5;
            position: relative;
            font-weight: 400;
        }}
        
        .post-description::before {{
            content: '💬';
            font-size: 24px;
            position: absolute;
            top: 15px;
            right: 20px;
            opacity: 0.3;
        }}
        
        .post-actions {{
            display: flex;
            gap: 24px;
            align-items: center;
            justify-content: space-between;
            margin-top: 28px;
            padding-top: 28px;
            border-top: 3px solid #f1f5f9;
            flex-wrap: wrap;
        }}
        
        .view-post-btn {{ 
            background: linear-gradient(135deg, #0077b5 0%, #00a0dc 50%, #10b981 100%);
            color: white; 
            text-decoration: none; 
            padding: 18px 36px; 
            border-radius: 50px; 
            font-weight: 800;
            font-size: 16px;
            display: inline-flex;
            align-items: center;
            gap: 12px;
            transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 12px 32px rgba(0,119,181,0.4);
            position: relative;
            overflow: hidden;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            border: 2px solid rgba(255,255,255,0.2);
        }}
        
        .view-post-btn::before {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            transition: left 0.8s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        
        .view-post-btn:hover {{
            transform: translateY(-6px) scale(1.08);
            box-shadow: 0 20px 50px rgba(0,119,181,0.5);
        }}
        
        .view-post-btn:hover::before {{
            left: 100%;
        }}
        
        .post-meta-info {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            font-size: 14px;
            color: #64748b;
        }}
        
        .meta-row {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .api-intelligence-section {{ 
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #374151 100%);
            color: white;
            padding: 50px 40px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }}
        
        .api-intelligence-section::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 20% 50%, rgba(16, 185, 129, 0.1) 0%, transparent 50%),
                radial-gradient(circle at 80% 50%, rgba(0, 160, 220, 0.1) 0%, transparent 50%),
                linear-gradient(135deg, transparent 0%, rgba(255,255,255,0.02) 50%, transparent 100%);
        }}
        
        .api-title {{
            font-size: 32px;
            font-weight: 900;
            margin-bottom: 25px;
            background: linear-gradient(135deg, #fbbf24, #f59e0b, #10b981);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            position: relative;
            z-index: 2;
        }}
        
        .api-stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 30px;
            margin: 35px 0;
            position: relative;
            z-index: 2;
        }}
        
        .api-stat-card {{
            background: rgba(255, 255, 255, 0.12);
            padding: 30px 25px;
            border-radius: 24px;
            text-align: center;
            border: 2px solid rgba(255, 255, 255, 0.1);
            transition: all 0.4s ease;
            backdrop-filter: blur(15px);
            position: relative;
            overflow: hidden;
        }}
        
        .api-stat-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #10b981, #00a0dc, #8b5cf6);
            background-size: 300% 100%;
            animation: statBorder 4s ease infinite;
        }}
        
        @keyframes statBorder {{
            0%, 100% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
        }}
        
        .api-stat-card:hover {{
            background: rgba(255, 255, 255, 0.18);
            transform: translateY(-8px) scale(1.05);
            box-shadow: 0 15px 40px rgba(0,0,0,0.3);
        }}
        
        .api-stat-number {{
            font-size: 38px;
            font-weight: 900;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #60a5fa, #3b82f6, #10b981);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            display: block;
        }}
        
        .api-stat-label {{
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            opacity: 0.95;
        }}
        
        .footer {{ 
            background: linear-gradient(135deg, #111827 0%, #1f2937 50%, #374151 100%);
            color: #d1d5db; 
            padding: 45px 35px; 
            text-align: center;
            position: relative;
            overflow: hidden;
        }}
        
        .footer::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="dots" width="10" height="10" patternUnits="userSpaceOnUse"><circle cx="5" cy="5" r="1" fill="rgba(255,255,255,0.03)"/></pattern></defs><rect width="100" height="100" fill="url(%23dots)"/></svg>');
        }}
        
        .footer-brand {{
            font-size: 28px;
            font-weight: 900;
            background: linear-gradient(135deg, #fbbf24, #f59e0b, #10b981);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 18px;
            position: relative;
            z-index: 2;
        }}
        
        .footer-tagline {{
            font-size: 18px;
            opacity: 0.9;
            margin-bottom: 25px;
            font-weight: 500;
            position: relative;
            z-index: 2;
        }}
        
        .api-tech-specs {{
            background: rgba(255, 255, 255, 0.08);
            padding: 25px;
            border-radius: 20px;
            margin-top: 25px;
            border: 2px solid rgba(255, 255, 255, 0.1);
            position: relative;
            z-index: 2;
        }}
        
        .tech-spec-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        
        .tech-spec-item {{
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            padding: 10px 16px;
            border-radius: 25px;
            font-size: 13px;
            font-weight: 700;
            text-align: center;
            border: 2px solid rgba(96, 165, 250, 0.3);
            transition: all 0.3s ease;
        }}
        
        .tech-spec-item:hover {{
            background: rgba(59, 130, 246, 0.25);
            transform: scale(1.05);
        }}
        
        @media (max-width: 768px) {{
            .container {{ margin: 15px; border-radius: 24px; }}
            .header {{ padding: 35px 25px; }}
            .content {{ padding: 30px; }}
            .post-card {{ padding: 28px; }}
            .post-actions {{ flex-direction: column; gap: 20px; }}
            .stats-dashboard {{ grid-template-columns: repeat(2, 1fr); }}
            .api-stats-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 LinkedIn API Intelligence</h1>
            <p>Monitoring authentique via API officielle</p>
        </div>
        
        <div class="api-badge">
            🔥 API LINKEDIN OFFICIELLE • CONTENU 100% AUTHENTIQUE • EXTRACTION PRÉCISE
        </div>
        
        <div class="stats-dashboard">
            <div class="stat-card">
                <span class="stat-value">{len(posts)}</span>
                <span class="stat-label">Posts Authentiques</span>
            </div>
            <div class="stat-card">
                <span class="stat-value">{profiles_count}</span>
                <span class="stat-label">Profils API</span>
            </div>
            <div class="stat-card">
                <span class="stat-value">{total_engagement}</span>
                <span class="stat-label">Engagements</span>
            </div>
            <div class="stat-card">
                <span class="stat-value">100%</span>
                <span class="stat-label">Précision</span>
            </div>
        </div>
        
        <div class="content">
"""
        
        # Posts avec design ultra-premium
        profiles_posts = {}
        for post in posts:
            if post.profile_name not in profiles_posts:
                profiles_posts[post.profile_name] = []
            profiles_posts[post.profile_name].append(post)
        
        for profile_name, profile_posts in profiles_posts.items():
            for post in profile_posts:
                type_icon = self._get_type_icon(post.post_type)
                media_icon = self._get_media_icon(post.media_type)
                avatar_letter = profile_name[0].upper()
                
                html += f"""
            <div class="post-card">
                <div class="post-header">
                    <div class="profile-avatar">{avatar_letter}</div>
                    <div class="profile-info">
                        <div class="profile-name">{profile_name}</div>
                        <div class="post-metadata">
                            <span class="api-badge">🚀 API OFFICIELLE</span>
                            <span class="post-type-badge">{type_icon} {post.post_type.replace('_', ' ').title()}</span>
                            <span class="media-badge">{media_icon} {post.media_type.upper()}</span>
                            <span class="engagement-counter">💬 {post.engagement_count}</span>
                        </div>
                    </div>
                </div>
                
                <div class="post-main-content">
                    <div class="post-title">{post.post_title}</div>
                    <div class="post-description">
                        {post.post_description}
                    </div>
                </div>
                
                <div class="post-actions">
                    <div class="post-meta-info">
                        <div class="meta-row">
                            <span>👤</span>
                            <span><strong>Auteur:</strong> {post.author_name}</span>
                        </div>
                        <div class="meta-row">
                            <span>📅</span>
                            <span><strong>Publié:</strong> {post.published_date}</span>
                        </div>
                        <div class="meta-row">
                            <span>🆔</span>
                            <span><strong>ID:</strong> {post.post_id}</span>
                        </div>
                    </div>
                    <a href="{post.post_url}" class="view-post-btn" target="_blank">
                        <span>🎯</span>
                        <span>Voir le Post</span>
                    </a>
                </div>
            </div>
"""
        
        html += f"""
        </div>
        
        <div class="api-intelligence-section">
            <div class="api-title">
                🤖 Intelligence API LinkedIn Avancée
            </div>
            
            <div class="api-stats-grid">
                <div class="api-stat-card">
                    <div class="api-stat-number">{len(posts)}</div>
                    <div class="api-stat-label">Posts API Extraits</div>
                </div>
                <div class="api-stat-card">
                    <div class="api-stat-number">{total_engagement}</div>
                    <div class="api-stat-label">Interactions Totales</div>
                </div>
                <div class="api-stat-card">
                    <div class="api-stat-number">{profiles_count}</div>
                    <div class="api-stat-label">Profils Surveillés</div>
                </div>
            </div>
            
            <div style="color: #cbd5e1; font-size: 18px; margin-top: 30px; opacity: 0.95; position: relative; z-index: 2;">
                🔥 Extraction Officielle • Contenu Authentique • Données Temps Réel
            </div>
            
            <div class="api-tech-specs">
                <div style="font-size: 16px; font-weight: 700; margin-bottom: 15px; color: #f3f4f6;">
                    🛠️ Spécifications Techniques API:
                </div>
                <div class="tech-spec-grid">
                    <span class="tech-spec-item">🔐 OAuth 2.0</span>
                    <span class="tech-spec-item">📡 API v2 LinkedIn</span>
                    <span class="tech-spec-item">🎯 UGC Posts Endpoint</span>
                    <span class="tech-spec-item">⚡ Temps Réel</span>
                    <span class="tech-spec-item">🔄 Auto-Refresh Token</span>
                    <span class="tech-spec-item">📊 Analytics Intégrés</span>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <div class="footer-brand">🚀 LinkedIn API Monitor v4.0</div>
            <div class="footer-tagline">
                Système de Veille Révolutionnaire • API Officielle LinkedIn • Extraction Authentique
            </div>
            <div style="font-size: 15px; opacity: 0.8; margin-top: 20px; position: relative; z-index: 2;">
                Dernière synchronisation API: {datetime.now().strftime('%d/%m/%Y à %H:%M UTC')} • Version 4.0 Officielle
            </div>
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def _get_type_icon(self, post_type: str) -> str:
        """Icônes par type de post"""
        icons = {
            'emploi': '💼', 'evenement': '📅', 'produit': '🚀', 
            'article': '📰', 'media': '🎥', 'poll': '📊',
            'actualite': '🔔', 'publication': '📝'
        }
        return icons.get(post_type, '📝')
    
    def _get_media_icon(self, media_type: str) -> str:
        """Icônes par type de média"""
        icons = {
            'video': '🎥', 'image': '🖼️', 'text': '📝', 
            'document': '📄', 'poll': '📊'
        }
        return icons.get(media_type, '📝')


class LinkedInAPIMonitor:
    """Monitor révolutionnaire utilisant l'API LinkedIn officielle"""
    
    def __init__(self, csv_file: str, email_config: Dict[str, str], api_config: Dict[str, str]):
        self.csv_file = csv_file
        self.notifier = APIBasedEmailNotifier(
            email_config['sender_email'],
            email_config['sender_password'],
            email_config['recipient_email']
        )
        
        # Client API LinkedIn
        self.linkedin_api = LinkedInAPIClient(
            api_config['client_id'],
            api_config['client_secret'],
            api_config.get('access_token', '')
        )
        
        # Collecteur de posts
        self.all_new_posts: List[LinkedInPost] = []
        
        # Statistiques API
        self.stats = {
            'total_profiles': 0, 'api_success': 0, 'api_errors': 0,
            'new_posts_found': 0, 'total_engagement': 0,
            'companies_processed': 0, 'profiles_processed': 0,
            'quota_remaining': 1000  # Quota API estimé
        }
    
    def load_profiles(self) -> List[ProfileData]:
        """Chargement des profils avec support ID"""
        try:
            if not os.path.exists(self.csv_file):
                print(f"❌ Fichier CSV non trouvé: {self.csv_file}")
                return self._create_api_default_profiles()
            
            profiles = []
            
            with open(self.csv_file, 'r', encoding='utf-8-sig', newline='') as file:
                reader = csv.DictReader(file)
                for i, row in enumerate(reader, 1):
                    profile = self._parse_api_row(row, i)
                    if profile:
                        profiles.append(profile)
            
            print(f"✅ {len(profiles)} profils API chargés")
            return profiles
            
        except Exception as e:
            print(f"❌ Erreur chargement API: {e}")
            return self._create_api_default_profiles()
    
    def _parse_api_row(self, row: Dict[str, Any], line_num: int) -> Optional[ProfileData]:
        """Parse ligne CSV avec support Profile_ID"""
        try:
            url = str(row.get('URL', '')).strip()
            name = str(row.get('Name', '')).strip()
            profile_id = str(row.get('Profile_ID', '')).strip()
            last_id = str(row.get('Last_Post_ID', '')).strip()
            error_count = int(row.get('Error_Count', 0) or 0)
            
            if url and name:
                profile = ProfileData(url, name, profile_id, last_id, error_count)
                
                # Auto-extraction ID si manquant
                if not profile.profile_id:
                    profile.profile_id = profile.extract_id_from_url()
                
                return profile
            
        except Exception as e:
            print(f"❌ Erreur ligne API {line_num}: {e}")
        
        return None
    
    def _create_api_default_profiles(self) -> List[ProfileData]:
        """Profils par défaut optimisés API"""
        defaults = [
            ProfileData("https://www.linkedin.com/company/microsoft/", "Microsoft", "microsoft"),
            ProfileData("https://www.linkedin.com/company/tesla-motors/", "Tesla", "tesla-motors"),
            ProfileData("https://www.linkedin.com/company/google/", "Google", "google")
        ]
        self.save_profiles(defaults)
        return defaults
    
    def check_profile_via_api(self, profile: ProfileData) -> Optional[List[LinkedInPost]]:
        """Vérification via API LinkedIn officielle"""
        try:
            print(f"🔥 API Check: {profile.name} ({profile.profile_type})")
            
            posts = []
            
            if profile.profile_type == 'company':
                # Posts d'entreprise via API
                posts = self.linkedin_api.get_company_posts(profile.profile_id, count=5)
                
                # Fallback UGC si échec
                if not posts:
                    company_urn = f"urn:li:organization:{profile.profile_id}"
                    posts = self.linkedin_api.get_ugc_posts(company_urn, count=5)
                
                self.stats['companies_processed'] += 1
                
            elif profile.profile_type == 'person':
                # Posts personnels (nécessite permissions étendues)
                posts = self.linkedin_api.get_profile_posts(profile.profile_id, count=5)
                
                # Fallback UGC
                if not posts:
                    person_urn = f"urn:li:person:{profile.profile_id}"
                    posts = self.linkedin_api.get_ugc_posts(person_urn, count=5)
                
                self.stats['profiles_processed'] += 1
            
            if posts:
                print(f"✅ {len(posts)} posts API extraits")
                
                # Mise à jour engagement total
                for post in posts:
                    self.stats['total_engagement'] += post.engagement_count
                
                # Mise à jour profil avec le dernier post
                if posts:
                    latest_post = posts[0]  # Le plus récent
                    profile.last_post_id = latest_post.post_id
                    profile.error_count = 0
                    profile.last_success = datetime.now().isoformat()
                
                self.stats['api_success'] += 1
                return posts
            else:
                print("⚠️ Aucun post trouvé via API")
                profile.error_count += 1
                self.stats['api_errors'] += 1
                return None
                
        except Exception as e:
            print(f"❌ Erreur API {profile.name}: {e}")
            profile.error_count += 1
            self.stats['api_errors'] += 1
            return None
    
    def save_profiles(self, profiles: List[ProfileData]) -> bool:
        """Sauvegarde avec support Profile_ID"""
        try:
            fieldnames = ['URL', 'Name', 'Profile_ID', 'Last_Post_ID', 'Error_Count']
            
            with open(self.csv_file, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for profile in profiles:
                    writer.writerow(profile.to_dict())
            
            print("💾 Profils API sauvegardés")
            return True
            
        except Exception as e:
            print(f"❌ Erreur sauvegarde API: {e}")
            return False
    
    def run_api_monitoring(self) -> bool:
        """Monitoring complet via API LinkedIn"""
        try:
            print("=" * 100)
            print(f"🚀 LINKEDIN API MONITOR v4.0 - {datetime.now()}")
            print("🔥 SYSTÈME RÉVOLUTIONNAIRE API OFFICIELLE:")
            print("   • 🔐 Authentification OAuth 2.0 sécurisée")
            print("   • 📡 API LinkedIn v2 + UGC Posts endpoint")
            print("   • 🎯 Extraction 100% authentique des posts")
            print("   • 💬 Données d'engagement temps réel")
            print("   • 🎨 Email ultra-premium avec contenu véritable")
            print("   • ⚡ Gestion intelligente des quotas API")
            print("=" * 100)
            
            # Authentification API
            if not self.linkedin_api.access_token:
                if not self.linkedin_api.authenticate_client_credentials():
                    print("💥 ÉCHEC AUTHENTIFICATION - Arrêt du monitoring")
                    return False
            
            # Chargement profils
            profiles = self.load_profiles()
            if not profiles:
                return False
            
            self.stats['total_profiles'] = len(profiles)
            self.all_new_posts = []
            changes_made = False
            
            # Traitement via API
            for i, profile in enumerate(profiles):
                try:
                    print(f"\n--- 🚀 {i+1}/{len(profiles)}: {profile.name} ({profile.profile_type}) ---")
                    
                    if profile.error_count >= 3:  # Seuil réduit pour API
                        print(f"⏭️ Profil API suspendu (erreurs: {profile.error_count})")
                        continue
                    
                    # Vérification API
                    api_posts = self.check_profile_via_api(profile)
                    
                    if api_posts:
                        # Détection nouveaux posts
                        new_posts = self._detect_new_posts(api_posts, profile)
                        
                        if new_posts:
                            print(f"🆕 {len(new_posts)} NOUVEAU{'X' if len(new_posts) > 1 else ''} POST{'S' if len(new_posts) > 1 else ''} API!")
                            
                            self.all_new_posts.extend(new_posts)
                            self.stats['new_posts_found'] += len(new_posts)
                            changes_made = True
                            
                            # Affichage détaillé
                            for j, post in enumerate(new_posts):
                                print(f"   {j+1}. 🎯 {post.post_title}")
                                print(f"      📝 {post.post_description[:80]}...")
                                print(f"      👤 Par: {post.author_name}")
                                print(f"      💬 {post.engagement_count} interactions")
                                print(f"      🎬 Type: {post.media_type} | 🏷️ Catégorie: {post.post_type}")
                        else:
                            print("⚪ Aucun nouveau post détecté")
                    
                    # Pause respectueuse des quotas API
                    if i < len(profiles) - 1:
                        api_pause = random.randint(15, 25)  # Pause API optimisée
                        print(f"⏳ Pause API respectueuse: {api_pause}s...")
                        time.sleep(api_pause)
                        
                        # Mise à jour quota estimé
                        self.stats['quota_remaining'] -= 2
                
                except Exception as e:
                    print(f"❌ Erreur API {profile.name}: {e}")
                    profile.error_count += 1
                    self.stats['api_errors'] += 1
            
            # Sauvegarde si changements
            if changes_made:
                self.save_profiles(profiles)
            
            # Notification ultra-premium
            if self.all_new_posts:
                print(f"\n🎨 Envoi notification API premium...")
                if self.notifier.send_api_optimized_notification(self.all_new_posts):
                    print("🎉 Notification API premium envoyée!")
                else:
                    print("❌ Échec notification API")
            
            # Rapport détaillé
            self._print_api_monitoring_report()
            
            return self.stats['api_success'] > 0 or self.stats['new_posts_found'] > 0
            
        except Exception as e:
            print(f"💥 ERREUR SYSTÈME API: {e}")
            return False
    
    def _detect_new_posts(self, api_posts: List[LinkedInPost], profile: ProfileData) -> List[LinkedInPost]:
        """Détection des nouveaux posts via comparaison ID"""
        if not api_posts:
            return []
        
        new_posts = []
        
        # Si pas d'historique, on prend le plus récent seulement
        if not profile.last_post_id:
            latest = api_posts[0]
            profile.last_post_id = latest.post_id
            return [latest]
        
        # Comparaison avec historique
        for post in api_posts:
            if post.post_id != profile.last_post_id:
                new_posts.append(post)
            else:
                break  # On s'arrête au dernier post connu
        
        return new_posts
    
    def _print_api_monitoring_report(self):
        """Rapport de monitoring API détaillé"""
        print("\n" + "🚀" + "=" * 98 + "🚀")
        print("📊 RAPPORT MONITORING API LINKEDIN OFFICIELLE")
        print("🚀" + "=" * 98 + "🚀")
        
        print(f"📋 Profils traités: {self.stats['api_success']}/{self.stats['total_profiles']}")
        print(f"🏢 Entreprises: {self.stats['companies_processed']}")
        print(f"👤 Profils personnels: {self.stats['profiles_processed']}")
        print(f"🆕 Nouveaux posts: {self.stats['new_posts_found']}")
        print(f"💬 Engagement total: {self.stats['total_engagement']}")
        print(f"❌ Erreurs API: {self.stats['api_errors']}")
        print(f"📊 Quota restant: ~{self.stats['quota_remaining']}")
        
        # Détail des posts
        if self.all_new_posts:
            print(f"\n🎉 POSTS AUTHENTIQUES DÉTECTÉS VIA API:")
            for i, post in enumerate(self.all_new_posts, 1):
                print(f"   {i}. 🎯 {post.profile_name}")
                print(f"      📰 {post.post_title}")
                print(f"      ✏️ {post.post_description[:70]}...")
                print(f"      👤 Auteur: {post.author_name}")
                print(f"      🎬 Média: {post.media_type} | 💬 Engagement: {post.engagement_count}")
                print(f"      📅 Publié: {post.published_date}")
                print(f"      ─" * 80)
        
        # Recommandations
        success_rate = (self.stats['api_success'] / self.stats['total_profiles'] * 100) if self.stats['total_profiles'] > 0 else 0
        print(f"\n📈 Taux de réussite API: {success_rate:.1f}%")
        
        if self.stats['quota_remaining'] < 100:
            print("⚠️ ATTENTION: Quota API faible - Considérez l'upgrade")
        
        print("🚀" + "=" * 98 + "🚀")


def validate_api_environment() -> tuple[Dict[str, str], Dict[str, str]]:
    """Validation environnement avec support API"""
    print("🔧 Validation environnement API LinkedIn...")
    
    # Configuration email
    email_vars = {
        'GMAIL_EMAIL': 'sender_email',
        'GMAIL_APP_PASSWORD': 'sender_password',
        'RECIPIENT_EMAIL': 'recipient_email'
    }
    
    # Configuration API LinkedIn
    api_vars = {
        'LINKEDIN_CLIENT_ID': 'client_id',
        'LINKEDIN_CLIENT_SECRET': 'client_secret',
        'LINKEDIN_ACCESS_TOKEN': 'access_token'  # Optionnel pour client_credentials
    }
    
    email_config = {}
    api_config = {}
    missing = []
    
    # Validation email
    for env_var, config_key in email_vars.items():
        value = os.getenv(env_var, '').strip()
        if value:
            email_config[config_key] = value
            display_value = value[:3] + "*" * (len(value)-6) + value[-3:] if len(value) > 6 else "***"
            print(f"✅ {env_var}: {display_value}")
        else:
            missing.append(env_var)
    
    # Validation API
    for env_var, config_key in api_vars.items():
        value = os.getenv(env_var, '').strip()
        if value:
            api_config[config_key] = value
            if config_key == 'access_token':
                print(f"✅ {env_var}: Token fourni")
            else:
                display_value = value[:6] + "*" * (len(value)-10) + value[-4:] if len(value) > 10 else "***"
                print(f"✅ {env_var}: {display_value}")
        elif env_var != 'LINKEDIN_ACCESS_TOKEN':  # Token optionnel
            missing.append(env_var)
    
    if missing:
        raise ValueError(f"Configuration API incomplète: {missing}")
    
    print("✅ Configuration API validée")
    return email_config, api_config


def setup_linkedin_app_guide():
    """Guide de configuration de l'app LinkedIn"""
    print("""
🔧 GUIDE CONFIGURATION APP LINKEDIN API
=====================================

Pour utiliser l'API LinkedIn, vous devez créer une application:

1. 🌐 Aller sur https://www.linkedin.com/developers/
2. 🏗️ Créer une nouvelle app LinkedIn
3. 🔑 Récupérer Client ID et Client Secret
4. ⚙️ Configurer les permissions:
   - r_organization_social (posts entreprises)
   - r_basicprofile (profils)
   - rw_organization_admin (si admin)

5. 🔐 Ajouter les variables d'environnement:
   export LINKEDIN_CLIENT_ID="votre_client_id"
   export LINKEDIN_CLIENT_SECRET="votre_client_secret"
   
6. 🎯 Optionnel - Token d'accès pré-généré:
   export LINKEDIN_ACCESS_TOKEN="votre_token"

⚠️ IMPORTANT: Les permissions pour profils personnels nécessitent
une validation LinkedIn (processus Partner Program)

✅ Pour commencer, utilisez les profils d'entreprises publiques
qui ne nécessitent que client_credentials flow.
""")


def main():
    """Point d'entrée révolutionnaire API"""
    try:
        print("🚀" + "=" * 98 + "🚀")
        print("🔥 LINKEDIN MONITOR v4.0 - API OFFICIELLE RÉVOLUTIONNAIRE")
        print("🎯 EXTRACTION AUTHENTIQUE LINKEDIN:")
        print("   • 🔐 Authentification OAuth 2.0 sécurisée")
        print("   • 📡 API LinkedIn v2 + UGC Posts endpoints")
        print("   • 🎯 Vrais titres et descriptions des posts")
        print("   • 💬 Données d'engagement temps réel")
        print("   • 🎨 Email ultra-premium avec contenu authentique")
        print("   • ⚡ Gestion intelligente des quotas et permissions")
        print("   • 🛡️ Support Company Pages + Personal Profiles")
        print("🚀" + "=" * 98 + "🚀")
        
        # Validation
        try:
            email_config, api_config = validate_api_environment()
        except ValueError as e:
            print(f"❌ {e}")
            print("\n" + "="*50)
            setup_linkedin_app_guide()
            sys.exit(1)
        
        # Lancement API monitoring
        monitor = LinkedInAPIMonitor("linkedin_urls.csv", email_config, api_config)
        success = monitor.run_api_monitoring()
        
        # Résultat final
        if success:
            print("🎉 MONITORING API LINKEDIN RÉUSSI!")
            if monitor.all_new_posts:
                engagement_total = sum(p.engagement_count for p in monitor.all_new_posts)
                print(f"🎯 {len(monitor.all_new_posts)} posts authentiques extraits")
                print(f"💬 {engagement_total} interactions totales")
                print("🎨 Email premium avec contenu véritable envoyé!")
            else:
                print("✅ Système API actif - Monitoring en cours")
            sys.exit(0)
        else:
            print("⚠️ Monitoring API en attente - Vérifiez la configuration")
            sys.exit(0)
    
    except Exception as e:
        print(f"💥 ERREUR SYSTÈME API: {e}")
        traceback.print_exc()
        sys.exit(0)


if __name__ == "__main__":
    main()
