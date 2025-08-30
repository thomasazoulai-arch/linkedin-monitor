#!/usr/bin/env python3
"""
LinkedIn Monitor Agent - Version Production Optimisée CORRIGÉE
Améliorations:
- URLs directes vers les posts spécifiques
- Extraction de contenu améliorée avec fallbacks intelligents  
- Format email moderne et engageant
- Gestion optimisée des métadonnées LinkedIn
- CORRECTION: Toutes les erreurs de syntaxe résolues
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
from urllib.parse import urlparse, urljoin


class PostData(NamedTuple):
    """Structure pour un nouveau post détecté"""
    profile_name: str
    post_title: str
    post_description: str
    post_url: str
    detection_time: str
    post_id: str


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


class EnhancedPostExtractor:
    """Extracteur optimisé avec multiple stratégies d'extraction"""
    
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
        ]
    
    def extract_posts_with_urls(self, html_content: str, profile_url: str, profile_name: str) -> List[PostData]:
        """Extraction optimisée avec URLs directes des posts"""
        try:
            posts_data = []
            
            # Stratégie 1: Extraction via data-urn et URN patterns
            posts_data.extend(self._extract_via_urn_patterns(html_content, profile_name))
            
            # Stratégie 2: Extraction via métadonnées OpenGraph/JSON-LD
            if not posts_data:
                posts_data.extend(self._extract_via_metadata(html_content, profile_name))
            
            # Stratégie 3: Pattern matching avancé sur les éléments feed
            if not posts_data:
                posts_data.extend(self._extract_via_feed_patterns(html_content, profile_name))
            
            # Stratégie 4: Fallback avec content analysis
            if not posts_data:
                posts_data.extend(self._extract_fallback_with_smart_urls(html_content, profile_url, profile_name))
            
            return posts_data[:3]  # Limiter à 3 posts maximum
            
        except Exception as e:
            print(f"❌ Erreur extraction posts optimisée: {e}")
            return []
    
    def _extract_via_urn_patterns(self, html: str, profile_name: str) -> List[PostData]:
        """Extraction via URN LinkedIn (méthode la plus fiable)"""
        posts = []
        
        # Patterns URN LinkedIn ultra-précis
        urn_patterns = [
            r'urn:li:activity:(\d{10,})',
            r'data-urn[^>]*urn:li:activity:(\d{10,})',
            r'"activity":"(\d{10,})"',
            r'/feed/update/urn:li:activity:(\d{10,})',
            r'activityUrn":"urn:li:activity:(\d{10,})"'
        ]
        
        extracted_ids = set()
        
        for pattern in urn_patterns:
            matches = re.findall(pattern, html)
            for activity_id in matches:
                if activity_id not in extracted_ids and len(activity_id) >= 10:
                    extracted_ids.add(activity_id)
                    
                    # Extraction du contenu associé à cet ID
                    post_content = self._extract_content_for_activity(html, activity_id)
                    
                    if post_content:
                        post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}"
                        posts.append(PostData(
                            profile_name=profile_name,
                            post_title=post_content['title'],
                            post_description=post_content['description'],
                            post_url=post_url,
                            detection_time=datetime.now().strftime('%d/%m/%Y à %H:%M'),
                            post_id=activity_id
                        ))
                    
                    if len(posts) >= 3:  # Limiter à 3 posts
                        break
        
        print(f"🎯 URN extraction: {len(posts)} posts trouvés")
        return posts
    
    def _extract_content_for_activity(self, html: str, activity_id: str) -> Optional[Dict[str, str]]:
        """Extraction du contenu textuel pour un activity ID spécifique"""
        try:
            # Recherche de sections contenant l'activity ID
            activity_sections = []
            
            # Pattern pour identifier la section du post
            section_pattern = rf'urn:li:activity:{activity_id}[^>]*>(.*?)(?=urn:li:activity:\d{{10,}}|$)'
            matches = re.findall(section_pattern, html, re.DOTALL)
            
            if matches:
                activity_sections.extend(matches)
            
            # Fallback: recherche dans un rayon plus large
            if not activity_sections:
                fallback_pattern = rf'.{{0,2000}}urn:li:activity:{activity_id}.{{0,2000}}'
                fallback_matches = re.findall(fallback_pattern, html, re.DOTALL)
                activity_sections.extend(fallback_matches)
            
            # Extraction du titre et description depuis les sections
            for section in activity_sections:
                content = self._parse_post_content(section)
                if content['title'] or content['description']:
                    return content
            
            # Dernier fallback: contenu générique
            return {
                'title': 'Nouvelle publication',
                'description': f'Nouvelle activité détectée sur le profil LinkedIn (ID: {activity_id[:8]}...)'
            }
            
        except Exception as e:
            print(f"❌ Erreur extraction contenu pour {activity_id}: {e}")
            return None
    
    def _parse_post_content(self, section_html: str) -> Dict[str, str]:
        """Parse le contenu d'une section de post"""
        title = ""
        description = ""
        
        # Patterns pour le titre (première ligne significative)
        title_patterns = [
            r'<span[^>]*class="[^"]*break-words[^"]*"[^>]*>(.*?)</span>',
            r'<div[^>]*feed-shared-text[^>]*>(.*?)</div>',
            r'<span[^>]*dir="ltr"[^>]*>(.*?)</span>',
            r'<p[^>]*>(.*?)</p>'
        ]
        
        for pattern in title_patterns:
            matches = re.findall(pattern, section_html, re.DOTALL)
            for match in matches:
                clean_title = self._clean_html_text(match)
                if len(clean_title.strip()) > 15:  # Titre significatif
                    title = self._truncate_to_sentence(clean_title, 100)
                    break
            if title:
                break
        
        # Patterns pour la description (contenu complet)
        desc_patterns = [
            r'<span[^>]*class="[^"]*break-words[^"]*"[^>]*>(.*?)</span>',
            r'<div[^>]*update-components-text[^>]*>(.*?)</div>',
            r'<span[^>]*dir="ltr"[^>]*>(.*?)</span>'
        ]
        
        full_text = ""
        for pattern in desc_patterns:
            matches = re.findall(pattern, section_html, re.DOTALL)
            for match in matches:
                clean_text = self._clean_html_text(match)
                if len(clean_text.strip()) > 20:
                    full_text += " " + clean_text
        
        if full_text.strip():
            description = self._generate_smart_description(full_text.strip())
        
        return {
            'title': title or "Nouvelle publication",
            'description': description or "Nouvelle activité LinkedIn détectée"
        }
    
    def _extract_via_metadata(self, html: str, profile_name: str) -> List[PostData]:
        """Extraction via métadonnées OpenGraph et JSON-LD"""
        posts = []
        
        try:
            # Recherche JSON-LD LinkedIn
            json_pattern = r'<script type="application/ld\+json"[^>]*>(.*?)</script>'
            json_matches = re.findall(json_pattern, html, re.DOTALL)
            
            for json_content in json_matches:
                try:
                    data = json.loads(json_content)
                    if isinstance(data, dict) and 'url' in data:
                        # Vérifier si c'est un post LinkedIn
                        url = data.get('url', '')
                        if 'feed/update' in url or 'posts' in url:
                            title = data.get('headline', data.get('name', ''))
                            description = data.get('description', '')
                            
                            if title or description:
                                posts.append(PostData(
                                    profile_name=profile_name,
                                    post_title=title[:100] if title else "Nouvelle publication",
                                    post_description=description[:200] if description else "Contenu LinkedIn détecté",
                                    post_url=url,
                                    detection_time=datetime.now().strftime('%d/%m/%Y à %H:%M'),
                                    post_id=self._extract_id_from_url(url)
                                ))
                except json.JSONDecodeError:
                    continue
            
            print(f"🔍 Metadata extraction: {len(posts)} posts trouvés")
            return posts
            
        except Exception as e:
            print(f"❌ Erreur extraction metadata: {e}")
            return []
    
    def _extract_via_feed_patterns(self, html: str, profile_name: str) -> List[PostData]:
        """Extraction via patterns feed LinkedIn"""
        posts = []
        
        # Patterns feed avancés
        feed_patterns = [
            r'<div[^>]*class="[^"]*feed-shared-update-v2[^"]*"[^>]*data-urn="([^"]+)"[^>]*>(.*?)</div>',
            r'<article[^>]*data-id="([^"]+)"[^>]*>(.*?)</article>',
            r'<div[^>]*feed-shared-update[^>]*id="([^"]+)"[^>]*>(.*?)</div>'
        ]
        
        for pattern in feed_patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            
            for post_identifier, content in matches[:3]:
                activity_id = self._extract_activity_id(post_identifier)
                if activity_id:
                    parsed_content = self._parse_post_content(content)
                    
                    post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}"
                    
                    posts.append(PostData(
                        profile_name=profile_name,
                        post_title=parsed_content['title'],
                        post_description=parsed_content['description'],
                        post_url=post_url,
                        detection_time=datetime.now().strftime('%d/%m/%Y à %H:%M'),
                        post_id=activity_id
                    ))
        
        print(f"📰 Feed patterns: {len(posts)} posts trouvés")
        return posts
    
    def _extract_fallback_with_smart_urls(self, html: str, profile_url: str, profile_name: str) -> List[PostData]:
        """Fallback avec URLs intelligentes"""
        posts = []
        
        try:
            # Recherche de contenus textuels significatifs
            content_patterns = [
                r'<span[^>]*class="[^"]*break-words[^"]*"[^>]*>([^<]{30,300})</span>',
                r'<div[^>]*feed-shared-text[^>]*>([^<]{25,250})</div>',
                r'<p[^>]*>([^<]{20,200})</p>'
            ]
            
            found_contents = []
            for pattern in content_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for match in matches:
                    clean_text = self._clean_html_text(match)
                    if self._is_meaningful_content(clean_text):
                        found_contents.append(clean_text)
                        
                if len(found_contents) >= 3:
                    break
            
            # Création de posts avec URLs optimisées
            for i, content in enumerate(found_contents[:2]):
                # Génération d'un ID unique basé sur le contenu
                content_id = hashlib.md5(content.encode()).hexdigest()[:10]
                
                # URL optimisée (fallback intelligent)
                optimized_url = self._generate_smart_fallback_url(profile_url, content_id)
                
                title = self._truncate_to_sentence(content, 80)
                description = self._generate_smart_description(content)
                
                posts.append(PostData(
                    profile_name=profile_name,
                    post_title=title,
                    post_description=description,
                    post_url=optimized_url,
                    detection_time=datetime.now().strftime('%d/%m/%Y à %H:%M'),
                    post_id=content_id
                ))
            
            print(f"🔄 Fallback extraction: {len(posts)} posts créés")
            return posts
            
        except Exception as e:
            print(f"❌ Erreur fallback extraction: {e}")
            return []
    
    def _extract_activity_id(self, identifier: str) -> Optional[str]:
        """Extraction de l'ID d'activité depuis un identifiant"""
        # Patterns pour extraire l'ID numérique
        id_patterns = [
            r'urn:li:activity:(\d{10,})',
            r'activity:(\d{10,})',
            r'^(\d{10,})$'
        ]
        
        for pattern in id_patterns:
            match = re.search(pattern, identifier)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_id_from_url(self, url: str) -> str:
        """Extraction ID depuis URL"""
        id_match = re.search(r'activity:(\d+)', url)
        return id_match.group(1) if id_match else hashlib.md5(url.encode()).hexdigest()[:10]
    
    def _generate_smart_fallback_url(self, profile_url: str, content_id: str) -> str:
        """Génération d'URL intelligente en fallback"""
        try:
            # Pour les pages entreprise
            if '/company/' in profile_url:
                company_match = re.search(r'/company/([^/]+)', profile_url)
                if company_match:
                    company_name = company_match.group(1)
                    return f"https://www.linkedin.com/company/{company_name}/posts/"
            
            # Pour les profils personnels
            elif '/in/' in profile_url:
                profile_match = re.search(r'/in/([^/]+)', profile_url)
                if profile_match:
                    profile_name = profile_match.group(1)
                    return f"https://www.linkedin.com/in/{profile_name}/recent-activity/all/"
            
            # Fallback général
            return profile_url.rstrip('/') + '/'
            
        except Exception:
            return profile_url
    
    def _is_meaningful_content(self, text: str) -> bool:
        """Vérifie si le contenu est significatif"""
        if len(text.strip()) < 20:
            return False
        
        # Filtrer les contenus non-pertinents
        noise_patterns = [
            r'^(Voir|View|Click|Cliquez|Se connecter|Login)',
            r'(cookie|privacy|politique)',
            r'^(Home|Accueil|Menu)$',
            r'^\d+\s*(likes?|commentaires?|partages?)$'
        ]
        
        for pattern in noise_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        
        return True
    
    def _truncate_to_sentence(self, text: str, max_length: int) -> str:
        """Troncature intelligente à la phrase"""
        if len(text) <= max_length:
            return text
        
        # Chercher la fin de phrase la plus proche
        sentences = re.split(r'[.!?]+\s+', text)
        if sentences and len(sentences[0]) <= max_length:
            return sentences[0].strip() + "."
        
        # Fallback: couper aux mots
        words = text.split()
        result = ""
        for word in words:
            if len(result + " " + word) <= max_length - 3:
                result += " " + word if result else word
            else:
                break
        
        return result.strip() + "..." if result else text[:max_length-3] + "..."
    
    def _generate_smart_description(self, text: str) -> str:
        """Génération de description intelligente (1-3 lignes)"""
        # Nettoyer le texte
        text = self._clean_html_text(text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        if len(text) <= 150:
            return text
        
        # Essayer de garder 2-3 phrases complètes
        sentences = re.split(r'[.!?]+\s+', text)
        description = ""
        
        for sentence in sentences[:3]:  # Max 3 phrases
            if len(description + " " + sentence) <= 200:
                description += ". " + sentence if description else sentence
            else:
                break
        
        if description:
            return description.strip() + "."
        
        # Fallback: mots avec ellipse
        words = text.split()
        description = ""
        for word in words:
            if len(description + " " + word) <= 180:
                description += " " + word if description else word
            else:
                break
        
        return description.strip() + "..." if description else "Nouvelle publication LinkedIn intéressante"
    
    def _clean_html_text(self, html_text: str) -> str:
        """Nettoyage avancé du texte HTML"""
        if not html_text:
            return ""
        
        # Suppression des balises HTML
        text = re.sub(r'<[^>]+>', '', html_text)
        
        # Décodage des entités HTML
        html_entities = {
            '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"',
            '&#39;': "'", '&nbsp;': ' ', '&hellip;': '...', '&rsquo;': "'",
            '&ldquo;': '"', '&rdquo;': '"', '&ndash;': '-', '&mdash;': '—'
        }
        
        for entity, char in html_entities.items():
            text = text.replace(entity, char)
        
        # Nettoyage des espaces et caractères spéciaux
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[\r\n\t]+', ' ', text)
        text = text.strip()
        
        return text


class ModernEmailNotifier:
    """Notificateur email avec design moderne et format optimisé"""
    
    def __init__(self, sender_email: str, sender_password: str, recipient_email: str):
        self.sender_email = sender_email
        self.sender_password = sender_password  
        self.recipient_email = recipient_email
    
    def send_modern_notification(self, all_new_posts: List[PostData]) -> bool:
        """Envoi de notification avec le nouveau format demandé"""
        try:
            if not all_new_posts:
                print("ℹ️ Aucun nouveau post à notifier")
                return True
            
            # Création du message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            # Sujet optimisé
            post_count = len(all_new_posts)
            profiles_count = len(set(post.profile_name for post in all_new_posts))
            
            if profiles_count == 1:
                profile_name = all_new_posts[0].profile_name
                msg['Subject'] = f"🔔 {profile_name} a publié {post_count} nouveau{'x' if post_count > 1 else ''} post{'s' if post_count > 1 else ''}"
            else:
                msg['Subject'] = f"🔔 {post_count} nouveaux posts de {profiles_count} profils LinkedIn"
            
            # Contenu texte simple
            text_content = self._build_modern_text_message(all_new_posts)
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            
            # Contenu HTML moderne
            html_content = self._build_modern_html_message(all_new_posts)
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Envoi SMTP
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            print(f"✅ Email moderne envoyé: {post_count} posts")
            return True
            
        except Exception as e:
            print(f"❌ Erreur envoi email: {e}")
            return False
    
    def _build_modern_text_message(self, posts: List[PostData]) -> str:
        """Message texte avec format demandé"""
        content = f"""🔔 NOUVELLES PUBLICATIONS LINKEDIN

📅 {datetime.now().strftime('%d/%m/%Y à %H:%M')}
📊 {len(posts)} nouvelle{'s' if len(posts) > 1 else ''} publication{'s' if len(posts) > 1 else ''}

"""
        
        # Grouper par profil
        profiles_posts = {}
        for post in posts:
            if post.profile_name not in profiles_posts:
                profiles_posts[post.profile_name] = []
            profiles_posts[post.profile_name].append(post)
        
        # Format demandé pour chaque profil
        for profile_name, profile_posts in profiles_posts.items():
            for post in profile_posts:
                content += f"""👤 {profile_name}
📑 Titre : {post.post_title}
✏️ Description : {post.post_description}
🔗 URL : {post.post_url}

"""
        
        content += """🤖 LinkedIn Monitor Agent
Surveillance automatisée de vos profils LinkedIn favoris
"""
        
        return content
    
    def _build_modern_html_message(self, posts: List[PostData]) -> str:
        """Message HTML moderne avec le format exact demandé"""
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LinkedIn Alert</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6; 
            color: #2c3e50; 
            background: #f8f9fa;
            padding: 20px;
        }}
        .container {{ 
            max-width: 650px; 
            margin: 0 auto; 
            background: white; 
            border-radius: 16px; 
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}
        .header {{ 
            background: linear-gradient(135deg, #0077b5 0%, #005885 100%);
            color: white; 
            padding: 30px 25px; 
            text-align: center;
        }}
        .header h1 {{ 
            font-size: 26px; 
            font-weight: 700; 
            margin-bottom: 8px;
        }}
        .header p {{ 
            opacity: 0.9; 
            font-size: 16px;
        }}
        .content {{ 
            padding: 25px;
        }}
        .post-item {{ 
            background: #ffffff;
            border: 1px solid #e1e8ed;
            border-radius: 12px; 
            padding: 24px; 
            margin-bottom: 20px;
            transition: all 0.3s ease;
            border-left: 4px solid #0077b5;
        }}
        .post-item:hover {{
            box-shadow: 0 4px 15px rgba(0,119,181,0.1);
            transform: translateY(-2px);
        }}
        .profile-name {{ 
            font-size: 18px; 
            font-weight: 700; 
            color: #0077b5; 
            margin-bottom: 15px;
            display: flex;
            align-items: center;
        }}
        .profile-emoji {{
            margin-right: 8px;
            font-size: 20px;
        }}
        .post-field {{ 
            margin-bottom: 12px; 
            display: flex;
            align-items: flex-start;
        }}
        .field-icon {{ 
            font-size: 16px; 
            margin-right: 10px; 
            margin-top: 2px;
            min-width: 20px;
        }}
        .field-label {{ 
            font-weight: 600; 
            color: #34495e; 
            margin-right: 8px;
            min-width: 85px;
        }}
        .field-content {{ 
            color: #2c3e50; 
            flex: 1;
            word-wrap: break-word;
        }}
        .post-title {{ 
            font-weight: 600;
            color: #2c3e50;
        }}
        .post-description {{ 
            color: #555; 
            font-style: italic; 
            line-height: 1.5;
        }}
        .post-url-container {{
            margin-top: 15px;
            text-align: center;
        }}
        .post-link {{ 
            background: linear-gradient(135deg, #0077b5, #005885);
            color: white; 
            text-decoration: none; 
            padding: 12px 24px; 
            border-radius: 25px; 
            font-weight: 600;
            display: inline-block;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0,119,181,0.3);
        }}
        .post-link:hover {{
            background: linear-gradient(135deg, #005885, #004766);
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(0,119,181,0.4);
        }}
        .stats {{ 
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            padding: 20px; 
            text-align: center; 
            color: #495057;
            border-top: 1px solid #dee2e6;
        }}
        .footer {{ 
            background: #2c3e50; 
            color: #ecf0f1; 
            padding: 20px; 
            text-align: center; 
            font-size: 14px;
        }}
        .footer a {{ 
            color: #3498db; 
            text-decoration: none;
        }}
        .divider {{
            height: 1px;
            background: linear-gradient(to right, transparent, #ddd, transparent);
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔔 Nouvelles Publications LinkedIn</h1>
            <p>Votre veille professionnelle en temps réel</p>
        </div>
        
        <div class="content">
"""
        
        # Grouper par profil
        profiles_posts = {}
        for post in posts:
            if post.profile_name not in profiles_posts:
                profiles_posts[post.profile_name] = []
            profiles_posts[post.profile_name].append(post)
        
        # Format exact demandé pour chaque post
        for profile_name, profile_posts in profiles_posts.items():
            for post in profile_posts:
                html += f"""
            <div class="post-item">
                <div class="profile-name">
                    <span class="profile-emoji">👤</span>{profile_name}
                </div>
                
                <div class="post-field">
                    <span class="field-icon">📑</span>
                    <span class="field-label">Titre :</span>
                    <span class="field-content post-title">{post.post_title}</span>
                </div>
                
                <div class="post-field">
                    <span class="field-icon">✏️</span>
                    <span class="field-label">Description :</span>
                    <span class="field-content post-description">{post.post_description}</span>
                </div>
                
                <div class="post-field">
                    <span class="field-icon">🔗</span>
                    <span class="field-label">URL :</span>
                    <span class="field-content">
                        <div class="post-url-container">
                            <a href="{post.post_url}" class="post-link" target="_blank">
                                👀 Voir le Post
                            </a>
                        </div>
                    </span>
                </div>
                
                <div class="divider"></div>
                <div style="text-align: center; color: #7f8c8d; font-size: 13px;">
                    📅 Détecté le {post.detection_time}
                </div>
            </div>
"""
        
        html += f"""
        </div>
        
        <div class="stats">
            <h3 style="color: #0077b5; margin-bottom: 10px;">📊 Résumé de veille</h3>
            <p><strong>{len(posts)}</strong> nouvelle{'s' if len(posts) > 1 else ''} publication{'s' if len(posts) > 1 else ''} de <strong>{len(profiles_posts)}</strong> profil{'s' if len(profiles_posts) > 1 else ''}</p>
            <p style="font-size: 14px; color: #6c757d; margin-top: 5px;">
                Surveillance automatique • {datetime.now().strftime('%d/%m/%Y à %H:%M UTC')}
            </p>
        </div>
        
        <div class="footer">
            <p><strong>🤖 LinkedIn Monitor Agent</strong></p>
            <p style="margin-top: 8px; opacity: 0.8;">
                Système de veille automatisé • Ne manquez aucune opportunité
            </p>
        </div>
    </div>
</body>
</html>
"""
        
        return html


class EnhancedContentAnalyzer:
    """Analyseur de contenu avec stratégies multiples"""
    
    @staticmethod
    def analyze_content_advanced(html_content: str, profile_url: str, profile_name: str) -> Dict[str, Any]:
        """Analyse avancée avec extraction optimisée"""
        try:
            # Utilisation du nouvel extracteur
            extractor = EnhancedPostExtractor()
            posts_data = extractor.extract_posts_with_urls(html_content, profile_url, profile_name)
            
            # Génération du hash basé sur les posts
            content_hash = EnhancedContentAnalyzer._generate_advanced_hash(posts_data, html_content)
            
            # Score d'activité amélioré
            activity_score = EnhancedContentAnalyzer._calculate_enhanced_activity_score(html_content, posts_data)
            
            return {
                'content_hash': content_hash,
                'activity_score': activity_score,
                'post_count': len(posts_data),
                'posts_data': posts_data,
                'timestamp': datetime.now().isoformat(),
                'analysis_version': '2.0'
            }
            
        except Exception as e:
            print(f"❌ Erreur analyse avancée: {e}")
            # Fallback vers analyse basique
            return {
                'content_hash': f"error_{hash(html_content[:1000]) if html_content else 'empty'}",
                'activity_score': 0,
                'post_count': 0,
                'posts_data': [],
                'timestamp': datetime.now().isoformat(),
                'analysis_version': '1.0'
            }
    
    @staticmethod
    def _generate_advanced_hash(posts_data: List[PostData], html_content: str) -> str:
        """Hash avancé basé sur les posts et métadonnées"""
        if posts_data:
            # Hash basé sur les IDs de posts et contenus
            combined = ""
            for post in posts_data:
                combined += f"{post.post_id}{post.post_title}{post.post_description[:50]}"
            return hashlib.sha256(combined.encode('utf-8')).hexdigest()[:20]
        else:
            # Fallback: hash basé sur le contenu général
            content_sample = html_content[:2000] if html_content else ""
            return hashlib.sha256(content_sample.encode('utf-8')).hexdigest()[:20]
    
    @staticmethod
    def _calculate_enhanced_activity_score(html_content: str, posts_data: List[PostData]) -> int:
        """Score d'activité amélioré"""
        base_score = len(posts_data) * 15  # 15 points par post détecté
        
        # Bonus pour indicateurs d'activité
        activity_indicators = [
            r'feed-shared-update-v2',
            r'urn:li:activity:',
            r'posted.*ago',
            r'published.*ago',
            r'shared.*ago'
        ]
        
        for pattern in activity_indicators:
            matches = len(re.findall(pattern, html_content, re.IGNORECASE))
            base_score += matches * 2
        
        return min(base_score, 100)  # Plafonner à 100


class OptimizedLinkedInMonitor:
    """Agent LinkedIn optimisé avec toutes les améliorations"""
    
    def __init__(self, csv_file: str, email_config: Dict[str, str]):
        self.csv_file = csv_file
        self.notifier = ModernEmailNotifier(
            email_config['sender_email'],
            email_config['sender_password'],
            email_config['recipient_email']
        )
        
        # Session HTTP optimisée
        self.session = self._create_optimized_session()
        
        # Collecteur de posts
        self.all_new_posts: List[PostData] = []
        
        # Statistiques détaillées
        self.stats = {
            'total': 0,
            'success': 0,
            'changes': 0,
            'new_posts': 0,
            'errors': 0,
            'url_optimizations': 0
        }
    
    def _create_optimized_session(self) -> requests.Session:
        """Création d'une session HTTP optimisée pour LinkedIn"""
        session = requests.Session()
        
        # Headers optimisés pour LinkedIn
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Connection': 'keep-alive'
        })
        
        return session
    
    def load_profiles(self) -> List[ProfileData]:
        """Chargement des profils (méthode existante optimisée)"""
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
        """Parse une ligne CSV en ProfileData"""
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
        """Validation d'URL LinkedIn"""
        patterns = [
            r'^https://www\.linkedin\.com/company/[^/]+/?(?:posts/?)?',
            r'^https://www\.linkedin\.com/in/[^/]+/?'
        ]
        return any(re.match(pattern, url) for pattern in patterns)
    
    def _create_default_profiles(self) -> List[ProfileData]:
        """Création de profils par défaut"""
        defaults = [
            ProfileData("https://www.linkedin.com/company/microsoft/", "Microsoft"),
            ProfileData("https://www.linkedin.com/company/tesla-motors/", "Tesla"), 
            ProfileData("https://www.linkedin.com/company/google/", "Google")
        ]
        print("📝 Création de profils par défaut")
        self.save_profiles(defaults)
        return defaults
    
    def check_profile_optimized(self, profile: ProfileData) -> Optional[Dict[str, Any]]:
        """Vérification optimisée d'un profil"""
        try:
            print(f"🔍 Vérification optimisée: {profile.name}")
            
            # URLs multiples pour maximiser les chances de succès
            check_urls = self._generate_multiple_urls(profile.url)
            
            best_analysis = None
            for i, url in enumerate(check_urls):
                print(f"   🌐 Tentative URL {i+1}: {url}")
                
                response = self._make_enhanced_request(url)
                if response and response.status_code == 200:
                    # Analyse avec le nouvel extracteur
                    analysis = EnhancedContentAnalyzer.analyze_content_advanced(
                        response.text, profile.url, profile.name
                    )
                    
                    if analysis['posts_data']:  # Posts détectés
                        print(f"   ✅ Succès: {analysis['post_count']} posts, Score: {analysis['activity_score']}")
                        best_analysis = analysis
                        self.stats['url_optimizations'] += 1
                        break
                    elif not best_analysis:  # Garder la meilleure analyse même sans posts
                        best_analysis = analysis
                
                # Pause entre tentatives
                if i < len(check_urls) - 1:
                    time.sleep(5)
            
            if best_analysis:
                profile.error_count = 0
                return best_analysis
            else:
                print(f"   ❌ Aucune URL fonctionnelle")
                profile.error_count += 1
                return None
                
        except Exception as e:
            print(f"❌ Erreur vérification {profile.name}: {e}")
            profile.error_count += 1
            return None
    
    def _generate_multiple_urls(self, base_url: str) -> List[str]:
        """Génération de multiples URLs de test"""
        urls = []
        
        if '/company/' in base_url:
            # Pour les entreprises
            company_match = re.search(r'/company/([^/]+)', base_url)
            if company_match:
                company_id = company_match.group(1)
                urls.extend([
                    f"https://www.linkedin.com/company/{company_id}/posts/",
                    f"https://www.linkedin.com/company/{company_id}/",
                    f"https://www.linkedin.com/company/{company_id}/feed/",
                    base_url
                ])
        
        elif '/in/' in base_url:
            # Pour les profils personnels
            profile_match = re.search(r'/in/([^/]+)', base_url)
            if profile_match:
                profile_id = profile_match.group(1)
                urls.extend([
                    f"https://www.linkedin.com/in/{profile_id}/recent-activity/all/",
                    f"https://www.linkedin.com/in/{profile_id}/",
                    f"https://www.linkedin.com/in/{profile_id}/detail/recent-activity/",
                    base_url
                ])
        
        # Ajouter l'URL originale si pas déjà présente
        if base_url not in urls:
            urls.append(base_url)
        
        return urls[:4]  # Limiter à 4 tentatives max
    
    def _make_enhanced_request(self, url: str) -> Optional[requests.Response]:
        """Requête HTTP améliorée avec rotation User-Agent"""
        for attempt in range(2):  # Réduire à 2 tentatives par URL
            try:
                # Rotation des User-Agents
                ua_index = attempt % len(EnhancedPostExtractor().user_agents)
                self.session.headers['User-Agent'] = EnhancedPostExtractor().user_agents[ua_index]
                
                response = self.session.get(url, timeout=25)
                
                if response.status_code == 429:  # Rate limiting
                    wait_time = 30 + (attempt * 15)
                    print(f"   ⏰ Rate limit, attente {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 200:
                    return response
                else:
                    print(f"   ⚠️ Status {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                print(f"   ❌ Tentative {attempt + 1}: {e}")
                if attempt < 1:
                    time.sleep(8)
        
        return None
    
    def save_profiles(self, profiles: List[ProfileData]) -> bool:
        """Sauvegarde des profils"""
        try:
            fieldnames = ['URL', 'Name', 'Last_Post_ID', 'Error_Count']
            
            with open(self.csv_file, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for profile in profiles:
                    writer.writerow(profile.to_dict())
            
            print("💾 Profils sauvegardés avec succès")
            return True
            
        except Exception as e:
            print(f"❌ Erreur sauvegarde: {e}")
            return False
    
    def run_optimized_monitoring(self) -> bool:
        """Cycle de monitoring optimisé"""
        try:
            print("=" * 85)
            print(f"🚀 LINKEDIN MONITORING OPTIMISÉ - {datetime.now()}")
            print("🔥 Nouvelles fonctionnalités activées:")
            print("   • 🎯 URLs directes vers les posts")
            print("   • 📧 Format email moderne et lisible") 
            print("   • 🔍 Extraction multi-stratégies")
            print("   • ⚡ Performance améliorée")
            print("=" * 85)
            
            # Chargement des profils
            profiles = self.load_profiles()
            if not profiles:
                print("❌ Aucun profil à surveiller")
                return False
            
            self.stats['total'] = len(profiles)
            changes_made = False
            self.all_new_posts = []
            
            # Traitement optimisé de chaque profil
            for i, profile in enumerate(profiles):
                try:
                    print(f"\n--- 📊 {i+1}/{len(profiles)}: {profile.name} ---")
                    print(f"🔗 URL base: {profile.url}")
                    
                    if profile.error_count >= 5:
                        print(f"⏭️ Profil ignoré (trop d'erreurs: {profile.error_count})")
                        continue
                    
                    # Vérification avec extraction optimisée
                    analysis = self.check_profile_optimized(profile)
                    
                    if analysis:
                        self.stats['success'] += 1
                        current_hash = analysis['content_hash']
                        
                        # Détection de changement
                        if profile.last_post_id != current_hash:
                            print(f"🆕 CHANGEMENT DÉTECTÉ!")
                            print(f"   📊 Ancienne signature: {profile.last_post_id[:15]}...")
                            print(f"   📊 Nouvelle signature: {current_hash[:15]}...")
                            
                            self.stats['changes'] += 1
                            changes_made = True
                            
                            # Ajout des nouveaux posts
                            new_posts = analysis.get('posts_data', [])
                            if new_posts:
                                self.all_new_posts.extend(new_posts)
                                self.stats['new_posts'] += len(new_posts)
                                print(f"   📝 {len(new_posts)} nouveau{'x' if len(new_posts) > 1 else ''} post{'s' if len(new_posts) > 1 else ''} avec URLs optimisées")
                                
                                # Affichage des détails
                                for j, post in enumerate(new_posts):
                                    print(f"      📑 Post {j+1}: {post.post_title[:50]}...")
                                    print(f"      🔗 URL: {post.post_url}")
                            
                            # Mise à jour
                            profile.last_post_id = current_hash
                        else:
                            print("⚪ Aucun changement détecté")
                    else:
                        self.stats['errors'] += 1
                        print(f"   ❌ Échec analyse (erreurs: {profile.error_count})")
                    
                    # Pause intelligente entre profils
                    if i < len(profiles) - 1:
                        pause = 12 + (i % 4) * 3  # 12-24 secondes
                        print(f"⏳ Pause stratégique: {pause}s...")
                        time.sleep(pause)
                
                except Exception as e:
                    print(f"❌ Erreur critique {profile.name}: {e}")
                    self.stats['errors'] += 1
                    profile.error_count += 1
            
            # Sauvegarde si modifications
            if changes_made:
                print(f"\n💾 Sauvegarde des modifications...")
                self.save_profiles(profiles)
            
            # Notification groupée moderne
            if self.all_new_posts:
                print(f"\n📧 Préparation notification moderne...")
                print(f"   📝 Posts à notifier: {len(self.all_new_posts)}")
                
                for post in self.all_new_posts:
                    print(f"   • {post.profile_name}: {post.post_title[:40]}...")
                
                if self.notifier.send_modern_notification(self.all_new_posts):
                    print("✅ Notification moderne envoyée avec succès!")
                else:
                    print("❌ Échec notification")
            else:
                print("\n📧 Aucun nouveau post - Pas de notification")
            
            # Rapport final détaillé
            self._print_detailed_report()
            
            return self.stats['success'] > 0
            
        except Exception as e:
            print(f"💥 ERREUR SYSTÈME CRITIQUE: {e}")
            traceback.print_exc()
            return False
    
    def _print_detailed_report(self):
        """Rapport final optimisé"""
        print("\n" + "🎯" + "=" * 83 + "🎯")
        print("📊 RAPPORT DÉTAILLÉ - VERSION OPTIMISÉE")
        print("🎯" + "=" * 83 + "🎯")
        
        print(f"📋 Profils traités: {self.stats['success']}/{self.stats['total']}")
        print(f"🆕 Changements détectés: {self.stats['changes']}")
        print(f"📝 Nouveaux posts avec URLs: {self.stats['new_posts']}")
        print(f"🎯 Optimisations URL réussies: {self.stats['url_optimizations']}")
        print(f"❌ Erreurs: {self.stats['errors']}")
        
        success_rate = (self.stats['success'] / self.stats['total']) * 100 if self.stats['total'] > 0 else 0
        print(f"📈 Taux de succès: {success_rate:.1f}%")
        
        if self.all_new_posts:
            print(f"\n🚀 POSTS DÉTECTÉS AVEC URLS OPTIMISÉES:")
            for post in self.all_new_posts:
                print(f"   👤 {post.profile_name}")
                print(f"   📑 {post.post_title}")
                print(f"   🔗 {post.post_url}")
                print(f"   ─" * 50)
        
        optimization_rate = (self.stats['url_optimizations'] / max(self.stats['success'], 1)) * 100
        print(f"🎯 Taux d'optimisation URL: {optimization_rate:.1f}%")
        
        print("🎯" + "=" * 83 + "🎯")


def validate_environment() -> Dict[str, str]:
    """Validation de l'environnement"""
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
    """Point d'entrée principal optimisé"""
    try:
        print("🎯" + "=" * 83 + "🎯")
        print("🤖 LINKEDIN MONITOR AGENT - VERSION OPTIMISÉE 2.0")
        print("🔥 NOUVELLES FONCTIONNALITÉS:")
        print("   • 🎯 URLs directes vers les posts LinkedIn")
        print("   • 📧 Format email moderne et engageant")
        print("   • 🔍 Extraction multi-stratégies intelligente")
        print("   • ⚡ Performance et fiabilité améliorées")
        print("   • 🎨 Interface responsive et professionnelle")
        print("🎯" + "=" * 83 + "🎯")
        
        # Validation
        email_config = validate_environment()
        
        # Mode debug
        debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
        if debug_mode:
            print("🐛 MODE DEBUG ACTIVÉ")
        
        # Lancement du monitoring optimisé
        monitor = OptimizedLinkedInMonitor("linkedin_urls.csv", email_config)
        success = monitor.run_optimized_monitoring()
        
        # Résultat final
        if success:
            print("🎉 MONITORING OPTIMISÉ TERMINÉ AVEC SUCCÈS!")
            if monitor.all_new_posts:
                print(f"🚀 {len(monitor.all_new_posts)} nouveaux posts avec URLs directes")
                print("📧 Notification au format moderne envoyée")
            else:
                print("✅ Surveillance active - Aucun nouveau contenu")
            sys.exit(0)
        else:
            print("💥 ÉCHEC DU MONITORING OPTIMISÉ")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n⏹️ Arrêt utilisateur")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 ERREUR SYSTÈME: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
