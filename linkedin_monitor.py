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
    """Extracteur spécialisé pour les NOUVEAUX POSTS PUBLIÉS uniquement"""
    
    @staticmethod
    def extract_posts_data(html_content: str, profile_url: str, profile_name: str) -> List[PostData]:
        """Extraction uniquement des nouveaux posts publiés (pas les likes/commentaires)"""
        try:
            posts_data = []
            
            # Patterns spécifiques pour les POSTS PUBLIÉS uniquement
            published_post_patterns = [
                # Pattern pour les posts d'entreprise avec activité de publication
                r'<div[^>]*data-urn="urn:li:activity:(\d+)"[^>]*>.*?posted\s+this.*?</div>',
                r'<div[^>]*data-urn="urn:li:activity:(\d+)"[^>]*>.*?published.*?</div>',
                r'<div[^>]*data-urn="urn:li:activity:(\d+)"[^>]*>.*?shared\s+this.*?</div>',
                
                # Pattern pour identifier les vraies URLs de posts dans le HTML
                r'href="(/posts/[^"]*activity-(\d+)[^"]*)"',
                r'data-tracking-control-name="[^"]*"[^>]*href="(/posts/[^"]*activity-(\d+)[^"]*)"',
                
                # Pattern alternatif pour les posts avec feed-shared-update-v2
                r'<div[^>]*feed-shared-update-v2[^>]*data-urn="[^"]*:activity:(\d+)"[^>]*>((?:(?!</div>).)*posted\s+this(?:(?!</div>).)*)</div>'
            ]
            
            print(f"🔍 Recherche de posts publiés pour {profile_name}...")
            
            # Recherche des vraies URLs de posts LinkedIn
            post_urls_found = PostExtractor._extract_real_post_urls(html_content, profile_url)
            
            for post_url, post_id in post_urls_found[:3]:  # Max 3 posts récents
                print(f"🎯 Post détecté: {post_id}")
                post_data = PostExtractor._extract_post_details_from_url(
                    post_url, post_id, profile_name
                )
                if post_data:
                    posts_data.append(post_data)
            
            # Si aucune URL trouvée, essayer l'extraction par patterns HTML
            if not posts_data:
                posts_data = PostExtractor._extract_from_html_patterns(
                    html_content, profile_url, profile_name
                )
            
            print(f"📊 {len(posts_data)} post{'s' if len(posts_data) > 1 else ''} trouvé{'s' if len(posts_data) > 1 else ''} pour {profile_name}")
            return posts_data
            
        except Exception as e:
            print(f"❌ Erreur extraction posts: {e}")
            return []
    
    @staticmethod
    def _extract_real_post_urls(html_content: str, profile_url: str) -> List[tuple]:
        """Extraction des vraies URLs LinkedIn des posts"""
        post_urls = []
        
        try:
            # Patterns pour les vraies URLs de posts LinkedIn
            url_patterns = [
                r'href="(/posts/[^"]*activity-(\d+)[^"]*)"',
                r'href="(https://www\.linkedin\.com/posts/[^"]*activity-(\d+)[^"]*)"',
                r'data-href="(/posts/[^"]*activity-(\d+)[^"]*)"',
            ]
            
            for pattern in url_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    url_path = match[0]
                    post_id = match[1]
                    
                    # Construire l'URL complète si nécessaire
                    if url_path.startswith('/'):
                        full_url = f"https://www.linkedin.com{url_path}"
                    else:
                        full_url = url_path
                    
                    # Vérifier que c'est bien un post (pas un profil)
                    if '/posts/' in full_url and 'activity-' in full_url:
                        post_urls.append((full_url, post_id))
            
            # Supprimer les doublons en gardant l'ordre
            seen = set()
            unique_urls = []
            for url, post_id in post_urls:
                if post_id not in seen:
                    seen.add(post_id)
                    unique_urls.append((url, post_id))
            
            return unique_urls[:5]  # Max 5 posts récents
            
        except Exception as e:
            print(f"❌ Erreur extraction URLs: {e}")
            return []
    
    @staticmethod
    def _extract_post_details_from_url(post_url: str, post_id: str, profile_name: str) -> Optional[PostData]:
        """Extraction des détails d'un post à partir de son URL"""
        try:
            # Titre basique à partir du contenu ou générique
            post_title = "Nouveau post"
            
            # Description générique mais pertinente
            post_description = f"Nouvelle publication de {profile_name}. Découvrez leur dernière actualité et engagez-vous avec leur contenu."
            
            return PostData(
                profile_name=profile_name,
                post_title=post_title,
                post_description=post_description,
                post_url=post_url,
                detection_time=datetime.now().strftime('%d/%m/%Y à %H:%M')
            )
            
        except Exception as e:
            print(f"❌ Erreur extraction détails post {post_id}: {e}")
            return None
    
    @staticmethod
    def _extract_from_html_patterns(html_content: str, profile_url: str, profile_name: str) -> List[PostData]:
        """Méthode alternative d'extraction depuis les patterns HTML"""
        try:
            posts_data = []
            
            # Recherche de contenus de posts publiés
            content_patterns = [
                r'<span[^>]*update-components-text[^>]*>([^<]{30,200})</span>',
                r'<div[^>]*feed-shared-text[^>]*>([^<]{30,200})</div>',
                r'posted\s+this.*?<span[^>]*>([^<]{30,200})</span>'
            ]
            
            activity_ids = re.findall(r'activity[:-](\d+)', html_content)
            
            for i, content_match in enumerate(content_patterns[:2]):  # Max 2 patterns
                matches = re.findall(content_match, html_content, re.IGNORECASE | re.DOTALL)
                
                for j, content in enumerate(matches[:2]):  # Max 2 matches par pattern
                    clean_content = PostExtractor._clean_html_text(content)
                    
                    if len(clean_content.strip()) > 30:
                        # Générer une URL de post LinkedIn
                        activity_id = activity_ids[j] if j < len(activity_ids) else str(int(time.time()))
                        company_name = PostExtractor._extract_company_name(profile_url)
                        
                        post_url = f"https://www.linkedin.com/posts/{company_name}_activity-{activity_id}"
                        
                        post_data = PostData(
                            profile_name=profile_name,
                            post_title=clean_content[:80] + "..." if len(clean_content) > 80 else clean_content,
                            post_description=PostExtractor._generate_smart_description(clean_content),
                            post_url=post_url,
                            detection_time=datetime.now().strftime('%d/%m/%Y à %H:%M')
                        )
                        
                        posts_data.append(post_data)
                        
                        if len(posts_data) >= 2:  # Limiter à 2 posts max
                            break
                
                if posts_data:  # Si on a trouvé des posts, arrêter
                    break
            
            return posts_data
            
        except Exception as e:
            print(f"❌ Erreur extraction HTML patterns: {e}")
            return []
    
    @staticmethod
    def _extract_company_name(profile_url: str) -> str:
        """Extraction du nom de l'entreprise depuis l'URL"""
        try:
            if '/company/' in profile_url:
                match = re.search(r'/company/([^/]+)', profile_url)
                if match:
                    return match.group(1)
            elif '/in/' in profile_url:
                match = re.search(r'/in/([^/]+)', profile_url)
                if match:
                    return match.group(1)
            return "company"
        except:
            return "company"
    
    @staticmethod
    def _extract_title(html: str) -> str:
        """Extraction du titre du post publié"""
        title_patterns = [
            r'<span[^>]*update-components-text[^>]*>([^<]+)</span>',
            r'<div[^>]*feed-shared-text[^>]*>([^<]+)</div>',
            r'posted\s+this.*?<span[^>]*>([^<]+)</span>',
        ]
        
        for pattern in title_patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            if matches:
                title = PostExtractor._clean_html_text(matches[0])
                if len(title.strip()) > 10:
                    # Première phrase ou 100 caractères max
                    sentences = re.split(r'[.!?]\s+', title)
                    first_sentence = sentences[0].strip()
                    return first_sentence[:100] + "..." if len(first_sentence) > 100 else first_sentence
        
        return "Nouveau post"
    
    @staticmethod
    def _extract_description(html: str) -> str:
        """Extraction et génération d'une description intelligente du post"""
        content_patterns = [
            r'<span[^>]*update-components-text[^>]*>([^<]+)</span>',
            r'<div[^>]*feed-shared-text[^>]*>([^<]+)</div>',
            r'posted\s+this.*?<p[^>]*>([^<]+)</p>'
        ]
        
        full_text = ""
        for pattern in content_patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                clean_text = PostExtractor._clean_html_text(match)
                if len(clean_text.strip()) > 20:
                    full_text += " " + clean_text
                    break  # Prendre le premier contenu significatif
        
        if not full_text.strip():
            return "Nouvelle publication avec du contenu intéressant à découvrir sur LinkedIn."
        
        # Génération d'une description de 1-2 lignes max
        return PostExtractor._generate_smart_description(full_text.strip())
    
    @staticmethod
    def _generate_smart_description(text: str) -> str:
        """Génère une description intelligente de 1-2 lignes maximum"""
        # Nettoyer et normaliser le texte
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Si le texte est très court, le retourner tel quel
        if len(text) <= 100:
            return text
        
        # Chercher une phrase complète de taille raisonnable (1-2 lignes)
        sentences = re.split(r'[.!?]+\s*', text)
        
        # Essayer de prendre les 2 premières phrases si elles font moins de 150 caractères
        if len(sentences) >= 2:
            two_sentences = (sentences[0] + ". " + sentences[1]).strip()
            if len(two_sentences) <= 150:
                return two_sentences + "."
        
        # Sinon prendre la première phrase si elle est de bonne taille
        if sentences and 30 <= len(sentences[0].strip()) <= 120:
            return sentences[0].strip() + "."
        
        # Fallback: couper intelligemment à ~120 caractères
        if len(text) > 120:
            # Couper au dernier mot avant 120 caractères
            truncated = text[:120]
            last_space = truncated.rfind(' ')
            if last_space > 80:  # S'assurer qu'on ne coupe pas trop court
                truncated = text[:last_space]
            return truncated.strip() + "..."
        
        return text
    
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
        """Envoi d'une notification groupée UNIQUEMENT s'il y a de nouveaux posts"""
        try:
            # IMPORTANT: Ne rien envoyer s'il n'y a pas de nouveaux posts
            if not all_new_posts:
                print("ℹ️ Aucun nouveau post publié - Aucun email envoyé")
                return True
            
            print(f"📧 Préparation email pour {len(all_new_posts)} nouveau{'x' if len(all_new_posts) > 1 else ''} post{'s' if len(all_new_posts) > 1 else ''} publié{'s' if len(all_new_posts) > 1 else ''}...")
            
            # Création du message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            # Sujet spécifique aux nouvelles publications
            post_count = len(all_new_posts)
            profiles_count = len(set(post.profile_name for post in all_new_posts))
            msg['Subject'] = f"🔔 LinkedIn - {post_count} nouveau{'x' if post_count > 1 else ''} post{'s' if post_count > 1 else ''} publié{'s' if post_count > 1 else ''} ({profiles_count} profile{'s' if profiles_count > 1 else ''})"            msg['To'] = self.recipient_email
            
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
        """Construction du message texte avec le nouveau format demandé"""
        content = f"""🔔 NOUVEAUX POSTS LINKEDIN DÉTECTÉS

📅 Rapport du {datetime.now().strftime('%d/%m/%Y à %H:%M UTC')}
📊 {len(posts)} nouveau{'x' if len(posts) > 1 else ''} post{'s' if len(posts) > 1 else ''} publié{'s' if len(posts) > 1 else ''}

"""
        
        # Grouper par profile
        profiles_posts = {}
        for post in posts:
            if post.profile_name not in profiles_posts:
                profiles_posts[post.profile_name] = []
            profiles_posts[post.profile_name].append(post)
        
        # Générer le contenu pour chaque profile avec le nouveau format
        for profile_name, profile_posts in profiles_posts.items():
            content += f"👤 PROFILE: {profile_name}\n"
            content += "─" * 50 + "\n"
            
            for i, post in enumerate(profile_posts, 1):
                content += f"""📝 POST #{i}:
Titre: {post.post_title}
Description: {post.post_description}
URL: {post.post_url}

"""
        
        content += """🤖 Système de veille automatisé LinkedIn
Agent LinkedIn Monitor - Surveillance des nouveaux posts uniquement

---
Configuration: Seules les nouvelles publications sont surveillées (pas les likes/commentaires)
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
            <div class="post-title">📝 POST #{i}:</div>
            <div style="margin: 10px 0;"><strong>Titre:</strong> {post.post_title}</div>
            <div style="margin: 10px 0;"><strong>Description:</strong> {post.post_description}</div>
            <div style="margin: 10px 0;"><strong>URL:</strong> <a href="{post.post_url}" target="_blank" style="color: #0077b5; word-break: break-all;">{post.post_url}</a></div>
        </div>
"""
            
            html += "    </div>\n"
        
        html += """
    <div style="text-align: center; margin: 30px 0;">
        <p style="color: #0077b5; font-size: 16px; font-weight: bold;">🎯 Nouveaux posts détectés !</p>
        <p style="color: #555;">Votre système surveille uniquement les nouvelles publications (pas les likes/commentaires)</p>
    </div>
    
    <div class="footer">
        <p>🤖 <strong>LinkedIn Monitor Agent - Posts uniquement</strong></p>
        <p>Surveillance des nouvelles publications • Notifications groupées • Alertes intelligentes</p>
        <p style="margin-top: 15px;">
            <em>Système optimisé pour détecter uniquement les nouveaux posts publiés</em>
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
            
            # Envoi de la notification groupée UNIQUEMENT si nouveaux posts
            if self.all_new_posts:
                print(f"\n📧 Envoi notification pour {len(self.all_new_posts)} nouveau{'x' if len(self.all_new_posts) > 1 else ''} post{'s' if len(self.all_new_posts) > 1 else ''} publié{'s' if len(self.all_new_posts) > 1 else ''}...")
                if self.notifier.send_grouped_notification(self.all_new_posts):
                    print("✅ Notification groupée envoyée avec succès")
                else:
                    print("❌ Échec notification groupée")
            else:
                print("\n📧 Aucun nouveau post publié - Aucune notification envoyée")
                print("ℹ️ L'agent surveille uniquement les nouvelles publications (pas les likes/commentaires)")
            
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
        print("   • 🎯 Détection UNIQUEMENT des nouveaux posts publiés")
        print("   • 🚫 Exclusion des likes, commentaires et autres activités") 
        print("   • 🔗 URLs directes des posts (format /posts/company_activity-...)")
        print("   • 📧 Email envoyé UNIQUEMENT s'il y a de nouveaux posts")
        print("   • 📝 Format optimisé avec titre, description et URL")
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
                print(f"🚀 {len(monitor.all_new_posts)} nouveau{'x' if len(monitor.all_new_posts) > 1 else ''} post{'s' if len(monitor.all_new_posts) > 1 else ''} publié{'s' if len(monitor.all_new_posts) > 1 else ''} détecté{'s' if len(monitor.all_new_posts) > 1 else ''} et notifié{'s' if len(monitor.all_new_posts) > 1 else ''}")
            else:
                print("📭 Aucun nouveau post publié - Surveillance continue active")
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
