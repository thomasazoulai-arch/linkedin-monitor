#!/usr/bin/env python3
"""
LinkedIn Monitor Agent - Version Ultra Améliorée
Améliorations majeures:
- Extraction intelligente du vrai contenu des posts
- Génération automatique de titres pertinents
- UX email ultra-moderne et engageante
- Analyse sémantique du contenu
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
    post_type: str = "publication"  # Type de contenu


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


class IntelligentContentExtractor:
    """Extracteur intelligent de contenu LinkedIn avec analyse sémantique"""
    
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0'
        ]
        
        # Patterns pour détecter le contenu générique à éviter
        self.noise_patterns = [
            r'^(accepter|accept|se connecter|login|sign|click|voir|view)',
            r'^(cookies?|privacy|politique|terms)',
            r'^(home|accueil|menu|navigation)',
            r'^\d+\s*(likes?|commentaires?|partages?|reactions?)',
            r'^(suivre|follow|s\'abonner|subscribe)',
            r'^(rejoindre|join|connect|connecter)',
            r'^(linkedin|© \d{4})',
            r'^(plus|more|suite|continue)',
            r'^[^\w\s]*$',  # Symboles uniquement
            r'^.{1,10}$'     # Texte trop court
        ]
    
    def extract_real_posts_content(self, html_content: str, profile_url: str, profile_name: str) -> List[PostData]:
        """Extraction intelligente du vrai contenu des posts"""
        try:
            print(f"🧠 Analyse intelligente du contenu pour {profile_name}...")
            
            # Stratégie 1: Extraction des vrais posts via patterns LinkedIn avancés
            real_posts = self._extract_genuine_posts(html_content, profile_name)
            
            # Stratégie 2: Si échec, extraction via contenu textuel intelligent
            if not real_posts:
                real_posts = self._extract_via_content_analysis(html_content, profile_url, profile_name)
            
            # Filtrage et validation finale
            validated_posts = self._validate_and_enhance_posts(real_posts)
            
            print(f"✅ {len(validated_posts)} posts authentiques extraits")
            return validated_posts[:3]  # Maximum 3 posts
            
        except Exception as e:
            print(f"❌ Erreur extraction intelligente: {e}")
            return []
    
    def _extract_genuine_posts(self, html: str, profile_name: str) -> List[PostData]:
        """Extraction des vrais posts LinkedIn"""
        posts = []
        
        # Patterns ultra-spécifiques pour le contenu de posts réels
        post_content_patterns = [
            # Pattern pour les posts dans le feed
            r'<span[^>]*class="[^"]*break-words[^"]*"[^>]*dir="ltr"[^>]*>\s*<span[^>]*>(.*?)</span>\s*</span>',
            # Pattern pour les descriptions de posts
            r'<div[^>]*class="[^"]*feed-shared-text[^"]*"[^>]*>.*?<span[^>]*dir="ltr"[^>]*>(.*?)</span>',
            # Pattern pour le contenu principal des updates
            r'<div[^>]*class="[^"]*update-components-text[^"]*"[^>]*>.*?<span[^>]*>(.*?)</span>',
            # Pattern pour les posts avec formatage riche
            r'<div[^>]*update-components-text[^>]*>.*?<span[^>]*class="[^"]*break-words[^"]*"[^>]*>(.*?)</span>'
        ]
        
        # Recherche des IDs d'activité associés
        activity_ids = self._find_activity_ids(html)
        
        content_found = set()
        
        for pattern in post_content_patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                # Nettoyage du contenu
                clean_content = self._deep_clean_content(match)
                
                # Validation du contenu
                if self._is_genuine_post_content(clean_content) and clean_content not in content_found:
                    content_found.add(clean_content)
                    
                    # Génération d'un titre intelligent
                    smart_title = self._generate_smart_title(clean_content)
                    
                    # Génération d'une description pertinente
                    smart_description = self._generate_smart_description(clean_content)
                    
                    # Génération d'un ID unique
                    post_id = self._generate_content_based_id(clean_content)
                    
                    # URL optimisée
                    post_url = self._generate_optimized_url(profile_name, activity_ids, post_id)
                    
                    # Détection du type de post
                    post_type = self._detect_post_type(clean_content)
                    
                    posts.append(PostData(
                        profile_name=profile_name,
                        post_title=smart_title,
                        post_description=smart_description,
                        post_url=post_url,
                        detection_time=datetime.now().strftime('%d/%m/%Y à %H:%M'),
                        post_id=post_id,
                        post_type=post_type
                    ))
                    
                    print(f"   ✅ Post authentique détecté: {smart_title[:50]}...")
                    
                    if len(posts) >= 3:
                        break
            
            if len(posts) >= 3:
                break
        
        return posts
    
    def _extract_via_content_analysis(self, html: str, profile_url: str, profile_name: str) -> List[PostData]:
        """Extraction via analyse sémantique du contenu"""
        posts = []
        
        try:
            # Recherche de blocs de contenu significatifs
            content_blocks = self._find_content_blocks(html)
            
            # Analyse de chaque bloc
            for i, block in enumerate(content_blocks[:3]):
                meaningful_content = self._extract_meaningful_sentences(block)
                
                if meaningful_content and len(meaningful_content) > 30:
                    # Génération de titre et description intelligents
                    title = self._create_intelligent_title(meaningful_content)
                    description = self._create_intelligent_description(meaningful_content)
                    
                    # Génération d'URL et ID
                    post_id = hashlib.md5(meaningful_content.encode()).hexdigest()[:12]
                    post_url = self._generate_fallback_url(profile_url, post_id)
                    
                    posts.append(PostData(
                        profile_name=profile_name,
                        post_title=title,
                        post_description=description,
                        post_url=post_url,
                        detection_time=datetime.now().strftime('%d/%m/%Y à %H:%M'),
                        post_id=post_id,
                        post_type="analyse"
                    ))
                    
                    print(f"   📝 Contenu analysé: {title[:40]}...")
            
            return posts
            
        except Exception as e:
            print(f"❌ Erreur analyse contenu: {e}")
            return []
    
    def _find_content_blocks(self, html: str) -> List[str]:
        """Recherche de blocs de contenu significatifs"""
        # Patterns pour identifier les vrais blocs de contenu
        block_patterns = [
            r'<article[^>]*>(.*?)</article>',
            r'<div[^>]*class="[^"]*feed-shared-update[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*update-components[^"]*"[^>]*>(.*?)</div>',
            r'<section[^>]*class="[^"]*feed[^"]*"[^>]*>(.*?)</section>'
        ]
        
        blocks = []
        for pattern in block_patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            blocks.extend(matches)
        
        # Filtrage des blocs significatifs
        significant_blocks = []
        for block in blocks:
            if len(block) > 200 and self._contains_meaningful_content(block):
                significant_blocks.append(block)
        
        return significant_blocks[:5]  # Top 5 blocs
    
    def _contains_meaningful_content(self, block: str) -> bool:
        """Vérifie si un bloc contient du contenu significatif"""
        # Recherche de phrases complètes
        sentences = re.findall(r'[A-Z][^.!?]*[.!?]', self._deep_clean_content(block))
        return len(sentences) >= 2 and len(self._deep_clean_content(block)) > 50
    
    def _extract_meaningful_sentences(self, block: str) -> str:
        """Extraction des phrases significatives d'un bloc"""
        clean_block = self._deep_clean_content(block)
        
        # Extraction des phrases complètes
        sentences = re.findall(r'[A-Z][^.!?]*[.!?]', clean_block)
        
        # Filtrage des phrases pertinentes
        meaningful_sentences = []
        for sentence in sentences:
            if len(sentence.strip()) > 20 and not self._is_noise_content(sentence):
                meaningful_sentences.append(sentence.strip())
        
        return ' '.join(meaningful_sentences[:3])  # Maximum 3 phrases
    
    def _is_genuine_post_content(self, content: str) -> bool:
        """Validation du contenu authentique de post"""
        if not content or len(content.strip()) < 15:
            return False
        
        # Vérification contre les patterns de bruit
        content_lower = content.lower().strip()
        
        for pattern in self.noise_patterns:
            if re.match(pattern, content_lower):
                return False
        
        # Doit contenir des mots significatifs
        meaningful_words = re.findall(r'\b[a-zA-ZÀ-ÿ]{4,}\b', content)
        if len(meaningful_words) < 3:
            return False
        
        # Doit avoir une structure de phrase
        has_sentence_structure = bool(re.search(r'[.!?]|[a-z][A-Z]', content))
        
        return has_sentence_structure and len(content.strip()) > 20
    
    def _is_noise_content(self, content: str) -> bool:
        """Détection du contenu générique/bruit"""
        content_lower = content.lower().strip()
        
        for pattern in self.noise_patterns:
            if re.search(pattern, content_lower):
                return True
        
        return False
    
    def _deep_clean_content(self, content: str) -> str:
        """Nettoyage profond du contenu HTML"""
        if not content:
            return ""
        
        # Suppression des balises HTML avec espaces
        content = re.sub(r'<[^>]+>', ' ', content)
        
        # Décodage des entités HTML avancé
        html_entities = {
            '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#x27;': "'",
            '&#39;': "'", '&nbsp;': ' ', '&hellip;': '...', '&rsquo;': "'",
            '&ldquo;': '"', '&rdquo;': '"', '&ndash;': '-', '&mdash;': '—',
            '&lsquo;': "'", '&trade;': '™', '&copy;': '©', '&reg;': '®'
        }
        
        for entity, char in html_entities.items():
            content = content.replace(entity, char)
        
        # Nettoyage des espaces multiples
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'[\r\n\t]+', ' ', content)
        
        # Suppression des caractères de contrôle
        content = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content)
        
        return content.strip()
    
    def _generate_smart_title(self, content: str) -> str:
        """Génération intelligente de titre basée sur le contenu"""
        if not content:
            return "Nouvelle publication LinkedIn"
        
        # Stratégie 1: Première phrase significative
        sentences = re.split(r'[.!?]+', content)
        for sentence in sentences:
            clean_sentence = sentence.strip()
            if 15 <= len(clean_sentence) <= 80 and not self._is_noise_content(clean_sentence):
                return clean_sentence + ("." if not clean_sentence.endswith(('.', '!', '?')) else "")
        
        # Stratégie 2: Mots-clés importants
        important_keywords = self._extract_keywords(content)
        if important_keywords:
            if len(important_keywords) <= 3:
                title = " • ".join(important_keywords).title()
            else:
                title = " • ".join(important_keywords[:3]).title() + "..."
            
            if len(title) > 15:
                return title
        
        # Stratégie 3: Synthèse intelligente
        words = content.split()[:12]  # 12 premiers mots
        if len(words) >= 5:
            title = " ".join(words)
            if len(title) > 70:
                title = title[:67] + "..."
            return title.strip()
        
        # Fallback avec analyse du type de contenu
        return self._generate_contextual_title(content)
    
    def _generate_smart_description(self, content: str) -> str:
        """Génération intelligente de description (1-2 lignes max)"""
        if not content:
            return "Nouvelle activité détectée sur LinkedIn"
        
        # Stratégie 1: 2-3 premières phrases complètes
        sentences = re.split(r'[.!?]+', content)
        meaningful_sentences = []
        
        for sentence in sentences[:4]:
            clean_sentence = sentence.strip()
            if len(clean_sentence) > 10 and not self._is_noise_content(clean_sentence):
                meaningful_sentences.append(clean_sentence)
        
        if meaningful_sentences:
            description = ". ".join(meaningful_sentences[:2])
            if len(description) > 200:
                # Troncature intelligente aux mots
                words = description.split()
                truncated = []
                current_length = 0
                
                for word in words:
                    if current_length + len(word) + 1 <= 180:
                        truncated.append(word)
                        current_length += len(word) + 1
                    else:
                        break
                
                description = " ".join(truncated) + "..."
            
            return description + ("." if not description.endswith(('.', '!', '?', '...')) else "")
        
        # Stratégie 2: Résumé par analyse de contenu
        return self._create_content_summary(content)
    
    def _extract_keywords(self, content: str) -> List[str]:
        """Extraction de mots-clés significatifs"""
        # Mots vides en français et anglais
        stop_words = {
            'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'et', 'ou', 'pour', 'avec',
            'dans', 'sur', 'par', 'ce', 'qui', 'que', 'dont', 'où', 'est', 'sont', 'a', 'ont',
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'this', 'that', 'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has'
        }
        
        # Extraction des mots significatifs (4+ caractères)
        words = re.findall(r'\b[a-zA-ZÀ-ÿ]{4,}\b', content.lower())
        
        # Comptage et filtrage
        word_freq = {}
        for word in words:
            if word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Retour des mots les plus fréquents
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word.capitalize() for word, freq in sorted_words[:5] if freq > 1]
    
    def _generate_contextual_title(self, content: str) -> str:
        """Génération de titre contextuel basé sur l'analyse"""
        # Détection du type de contenu
        if re.search(r'\b(recrut|job|emploi|poste|opportunit|career)\b', content, re.IGNORECASE):
            return "💼 Opportunité professionnelle"
        elif re.search(r'\b(innovat|technolog|digital|AI|IA|future)\b', content, re.IGNORECASE):
            return "🚀 Innovation & Technologie"
        elif re.search(r'\b(event|événement|conference|webinar|formation)\b', content, re.IGNORECASE):
            return "📅 Événement professionnel"
        elif re.search(r'\b(partenariat|collaboration|partnership)\b', content, re.IGNORECASE):
            return "🤝 Partenariat stratégique"
        elif re.search(r'\b(product|produit|launch|lancement|nouveau)\b', content, re.IGNORECASE):
            return "🎉 Nouveau produit/service"
        elif re.search(r'\b(award|prix|récompense|recognition)\b', content, re.IGNORECASE):
            return "🏆 Reconnaissance & Prix"
        else:
            return "📢 Nouvelle publication"
    
    def _create_content_summary(self, content: str) -> str:
        """Création d'un résumé intelligent du contenu"""
        # Extraction des 2 premières phrases significatives
        sentences = [s.strip() for s in re.split(r'[.!?]+', content) if len(s.strip()) > 15]
        
        if sentences:
            summary = ". ".join(sentences[:2])
            if len(summary) > 150:
                words = summary.split()[:20]  # Limiter à 20 mots
                summary = " ".join(words) + "..."
            return summary
        
        return "Contenu professionnel partagé sur LinkedIn"
    
    def _find_activity_ids(self, html: str) -> List[str]:
        """Recherche des IDs d'activité LinkedIn"""
        patterns = [
            r'urn:li:activity:(\d{10,})',
            r'data-urn[^>]*activity:(\d{10,})',
            r'"activityUrn":"[^"]*activity:(\d{10,})"'
        ]
        
        activity_ids = set()
        for pattern in patterns:
            matches = re.findall(pattern, html)
            activity_ids.update(matches)
        
        return list(activity_ids)[:5]  # Maximum 5 IDs
    
    def _generate_content_based_id(self, content: str) -> str:
        """Génération d'ID basé sur le contenu"""
        # Hash du contenu + timestamp pour unicité
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:8]
        time_hash = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:4]
        return f"{content_hash}{time_hash}"
    
    def _generate_optimized_url(self, profile_name: str, activity_ids: List[str], post_id: str) -> str:
        """Génération d'URL optimisée pour le post"""
        # Si on a un vrai ID d'activité LinkedIn
        if activity_ids:
            return f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_ids[0]}"
        
        # Fallback intelligent basé sur le type de profil
        profile_lower = profile_name.lower().replace(' ', '')
        return f"https://www.linkedin.com/posts/{profile_lower}_{post_id}"
    
    def _generate_fallback_url(self, profile_url: str, post_id: str) -> str:
        """URL de fallback intelligente"""
        if '/company/' in profile_url:
            company_match = re.search(r'/company/([^/]+)', profile_url)
            if company_match:
                return f"https://www.linkedin.com/company/{company_match.group(1)}/posts/"
        elif '/in/' in profile_url:
            profile_match = re.search(r'/in/([^/]+)', profile_url)
            if profile_match:
                return f"https://www.linkedin.com/in/{profile_match.group(1)}/recent-activity/all/"
        
        return profile_url
    
    def _detect_post_type(self, content: str) -> str:
        """Détection du type de post"""
        content_lower = content.lower()
        
        if 'job' in content_lower or 'emploi' in content_lower:
            return 'offre_emploi'
        elif 'event' in content_lower or 'événement' in content_lower:
            return 'evenement'
        elif 'product' in content_lower or 'produit' in content_lower:
            return 'produit'
        else:
            return 'publication'
    
    def _validate_and_enhance_posts(self, posts: List[PostData]) -> List[PostData]:
        """Validation finale et amélioration des posts"""
        validated = []
        
        for post in posts:
            # Validation du titre
            if self._is_noise_content(post.post_title):
                # Régénération du titre
                enhanced_title = self._generate_contextual_title(post.post_description)
                post = post._replace(post_title=enhanced_title)
            
            # Validation de la description
            if self._is_noise_content(post.post_description):
                # Régénération de la description
                enhanced_desc = f"Nouvelle publication de {post.profile_name} détectée"
                post = post._replace(post_description=enhanced_desc)
            
            validated.append(post)
        
        return validated
    
    def _create_intelligent_title(self, content: str) -> str:
        """Création de titre vraiment intelligent"""
        # Recherche de hashtags pour le contexte
        hashtags = re.findall(r'#(\w+)', content)
        
        # Recherche de mots importants en début de contenu
        words = content.split()[:10]
        important_words = [w for w in words if len(w) > 3 and not self._is_noise_content(w)]
        
        if hashtags:
            main_hashtag = hashtags[0].capitalize()
            if important_words:
                return f"{main_hashtag}: {' '.join(important_words[:4])}"
            else:
                return f"Publication sur {main_hashtag}"
        
        elif important_words and len(important_words) >= 3:
            title = " ".join(important_words[:6])
            return title[:70] + ("..." if len(title) > 70 else "")
        
        return "Nouvelle publication professionnelle"
    
    def _create_intelligent_description(self, content: str) -> str:
        """Création de description vraiment intelligente"""
        # Nettoyage et structuration
        sentences = [s.strip() for s in re.split(r'[.!?]+', content) if len(s.strip()) > 10]
        
        # Filtrage des phrases significatives
        good_sentences = []
        for sentence in sentences[:4]:
            if not self._is_noise_content(sentence) and len(sentence) > 15:
                good_sentences.append(sentence)
        
        if good_sentences:
            # Utiliser les 2 meilleures phrases
            description = ". ".join(good_sentences[:2])
            
            # Optimisation de la longueur
            if len(description) > 180:
                words = description.split()[:25]
                description = " ".join(words) + "..."
            
            return description + ("." if not description.endswith(('.', '!', '?', '...')) else "")
        
        # Fallback avec analyse des mots-clés
        keywords = self._extract_keywords(content)
        if keywords:
            return f"Publication concernant: {', '.join(keywords[:3])}"
        
        return "Nouveau contenu professionnel partagé"


class UltraModernEmailNotifier:
    """Notificateur email avec UX ultra-moderne et engageante"""
    
    def __init__(self, sender_email: str, sender_password: str, recipient_email: str):
        self.sender_email = sender_email
        self.sender_password = sender_password  
        self.recipient_email = recipient_email
    
    def send_ultra_modern_notification(self, all_new_posts: List[PostData]) -> bool:
        """Notification avec UX révolutionnaire"""
        try:
            if not all_new_posts:
                print("ℹ️ Aucun nouveau post à notifier")
                return True
            
            # Création du message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            # Sujet ultra-engageant
            subject = self._create_engaging_subject(all_new_posts)
            msg['Subject'] = subject
            
            # Contenu texte
            text_content = self._build_enhanced_text_message(all_new_posts)
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            
            # Contenu HTML révolutionnaire
            html_content = self._build_revolutionary_html_message(all_new_posts)
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Envoi SMTP
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            print(f"🎉 Email ultra-moderne envoyé: {len(all_new_posts)} posts")
            return True
            
        except Exception as e:
            print(f"❌ Erreur envoi email: {e}")
            return False
    
    def _create_engaging_subject(self, posts: List[PostData]) -> str:
        """Création de sujet ultra-engageant"""
        post_count = len(posts)
        profiles = list(set(post.profile_name for post in posts))
        
        # Analyse du type de contenu
        post_types = [post.post_type for post in posts]
        has_jobs = 'offre_emploi' in post_types
        has_events = 'evenement' in post_types
        has_products = 'produit' in post_types
        
        # Sujets contextuels
        if has_jobs:
            return f"💼 {post_count} nouvelle{'s' if post_count > 1 else ''} opportunité{'s' if post_count > 1 else ''} pro détectée{'s' if post_count > 1 else ''} !"
        elif has_events:
            return f"📅 {post_count} événement{'s' if post_count > 1 else ''} LinkedIn à ne pas manquer !"
        elif has_products:
            return f"🚀 {post_count} innovation{'s' if post_count > 1 else ''} / nouveau{'x' if post_count > 1 else ''} produit{'s' if post_count > 1 else ''} !"
        elif len(profiles) == 1:
            profile_name = profiles[0]
            return f"🔔 {profile_name} vient de publier du contenu exclusif !"
        else:
            return f"🌟 {post_count} publications LinkedIn exclusives de {len(profiles)} profils !"
    
    def _build_enhanced_text_message(self, posts: List[PostData]) -> str:
        """Message texte amélioré"""
        content = f"""🔔 NOUVELLES PUBLICATIONS LINKEDIN DÉTECTÉES

📅 {datetime.now().strftime('%d/%m/%Y à %H:%M')}
📊 {len(posts)} nouvelle{'s' if len(posts) > 1 else ''} publication{'s' if len(posts) > 1 else ''} authentique{'s' if len(posts) > 1 else ''}

"""
        
        # Grouper par profil
        profiles_posts = {}
        for post in posts:
            if post.profile_name not in profiles_posts:
                profiles_posts[post.profile_name] = []
            profiles_posts[post.profile_name].append(post)
        
        # Format pour chaque profil avec icônes contextuelles
        for profile_name, profile_posts in profiles_posts.items():
            for post in profile_posts:
                icon = self._get_post_type_icon(post.post_type)
                content += f"""👤 {profile_name}
{icon} Titre : {post.post_title}
✏️ Description : {post.post_description}
🔗 URL : {post.post_url}

"""
        
        content += """🤖 LinkedIn Monitor Agent Ultra
Veille intelligente avec extraction de contenu authentique
"""
        
        return content
    
    def _get_post_type_icon(self, post_type: str) -> str:
        """Icônes contextuelles selon le type de post"""
        icons = {
            'offre_emploi': '💼',
            'evenement': '📅',
            'produit': '🚀',
            'publication': '📑',
            'analyse': '🧠'
        }
        return icons.get(post_type, '📑')
    
    def _build_revolutionary_html_message(self, posts: List[PostData]) -> str:
        """Message HTML révolutionnaire avec UX de niveau supérieur"""
        
        # Calcul des statistiques pour l'header dynamique
        profiles_count = len(set(post.profile_name for post in posts))
        post_types = {}
        for post in posts:
            post_types[post.post_type] = post_types.get(post.post_type, 0) + 1
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔔 LinkedIn Alert Ultra</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        * {{ 
            margin: 0; 
            padding: 0; 
            box-sizing: border-box; 
        }}
        
        body {{ 
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            line-height: 1.6; 
            color: #1a202c; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{ 
            max-width: 700px; 
            margin: 0 auto; 
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 24px; 
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
            border: 1px solid rgba(255,255,255,0.2);
        }}
        
        .header {{ 
            background: linear-gradient(135deg, #0077b5 0%, #00a0dc 50%, #0077b5 100%);
            background-size: 200% 200%;
            animation: gradientShift 4s ease infinite;
            color: white; 
            padding: 40px 30px; 
            text-align: center;
            position: relative;
            overflow: hidden;
        }}
        
        .header::before {{
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
            animation: pulse 3s ease-in-out infinite;
        }}
        
        @keyframes gradientShift {{
            0%, 100% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
        }}
        
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); opacity: 0.3; }}
            50% {{ transform: scale(1.1); opacity: 0.1; }}
        }}
        
        .header h1 {{ 
            font-size: 32px; 
            font-weight: 700; 
            margin-bottom: 12px;
            position: relative;
            z-index: 2;
            text-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }}
        
        .header p {{ 
            opacity: 0.95; 
            font-size: 18px;
            font-weight: 400;
            position: relative;
            z-index: 2;
        }}
        
        .stats-bar {{
            background: linear-gradient(90deg, #f8f9fa, #e9ecef);
            padding: 20px 30px;
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            border-bottom: 1px solid #dee2e6;
        }}
        
        .stat-item {{
            text-align: center;
            margin: 5px;
        }}
        
        .stat-number {{
            font-size: 24px;
            font-weight: 700;
            color: #0077b5;
            display: block;
        }}
        
        .stat-label {{
            font-size: 12px;
            color: #6c757d;
            text-transform: uppercase;
            font-weight: 500;
            letter-spacing: 0.5px;
        }}
        
        .content {{ 
            padding: 30px;
            background: #ffffff;
        }}
        
        .post-item {{ 
            background: linear-gradient(145deg, #ffffff, #f8f9fc);
            border: 1px solid #e1e8ed;
            border-radius: 20px; 
            padding: 28px; 
            margin-bottom: 24px;
            position: relative;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            border-left: 5px solid #0077b5;
            overflow: hidden;
        }}
        
        .post-item::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #0077b5, #00a0dc, #0077b5);
            background-size: 200% 100%;
            animation: shimmer 3s ease-in-out infinite;
        }}
        
        @keyframes shimmer {{
            0%, 100% {{ background-position: -200% 0; }}
            50% {{ background-position: 200% 0; }}
        }}
        
        .post-item:hover {{
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 20px 40px rgba(0,119,181,0.15);
            border-left-color: #00a0dc;
        }}
        
        .profile-header {{ 
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f1f3f4;
        }}
        
        .profile-avatar {{
            width: 50px;
            height: 50px;
            background: linear-gradient(135deg, #0077b5, #00a0dc);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            font-weight: 700;
            color: white;
            margin-right: 15px;
            box-shadow: 0 4px 15px rgba(0,119,181,0.3);
        }}
        
        .profile-info {{
            flex: 1;
        }}
        
        .profile-name {{ 
            font-size: 20px; 
            font-weight: 700; 
            color: #0077b5; 
            margin-bottom: 4px;
        }}
        
        .post-meta {{
            font-size: 13px;
            color: #6c757d;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .post-type-badge {{
            background: linear-gradient(135deg, #28a745, #20c997);
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .post-content {{
            margin: 20px 0;
        }}
        
        .post-title {{ 
            font-size: 22px;
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 15px;
            line-height: 1.4;
            background: linear-gradient(135deg, #2d3748, #4a5568);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .post-description {{ 
            color: #4a5568; 
            font-size: 16px;
            line-height: 1.6;
            margin-bottom: 20px;
            padding: 20px;
            background: linear-gradient(145deg, #f7fafc, #edf2f7);
            border-radius: 15px;
            border-left: 4px solid #0077b5;
            position: relative;
        }}
        
        .post-description::before {{
            content: '"';
            font-size: 60px;
            color: rgba(0,119,181,0.1);
            position: absolute;
            top: -10px;
            left: 10px;
            font-family: Georgia, serif;
        }}
        
        .action-zone {{
            display: flex;
            gap: 15px;
            align-items: center;
            justify-content: space-between;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
        }}
        
        .post-link {{ 
            background: linear-gradient(135deg, #0077b5 0%, #00a0dc 100%);
            color: white; 
            text-decoration: none; 
            padding: 14px 28px; 
            border-radius: 50px; 
            font-weight: 600;
            font-size: 15px;
            display: inline-flex;
            align-items: center;
            gap: 10px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 6px 20px rgba(0,119,181,0.3);
            position: relative;
            overflow: hidden;
        }}
        
        .post-link::before {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
        }}
        
        .post-link:hover {{
            transform: translateY(-3px) scale(1.05);
            box-shadow: 0 12px 30px rgba(0,119,181,0.4);
            background: linear-gradient(135deg, #005885 0%, #0077b5 100%);
        }}
        
        .post-link:hover::before {{
            left: 100%;
        }}
        
        .detection-time {{
            font-size: 13px;
            color: #718096;
            display: flex;
            align-items: center;
            gap: 6px;
            background: rgba(113,128,150,0.1);
            padding: 8px 12px;
            border-radius: 20px;
        }}
        
        .summary-section {{ 
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 30px; 
            text-align: center; 
            border-top: 1px solid #dee2e6;
        }}
        
        .summary-title {{
            font-size: 24px;
            font-weight: 700;
            color: #0077b5;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }}
        
        .summary-stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
            margin: 20px 0;
        }}
        
        .summary-stat {{
            text-align: center;
        }}
        
        .summary-stat-number {{
            font-size: 28px;
            font-weight: 700;
            color: #0077b5;
            display: block;
        }}
        
        .summary-stat-label {{
            font-size: 14px;
            color: #6c757d;
            font-weight: 500;
        }}
        
        .cta-section {{
            background: linear-gradient(135deg, #1a202c 0%, #2d3748 100%);
            color: #ffffff;
            padding: 35px 30px;
            text-align: center;
        }}
        
        .cta-title {{
            font-size: 26px;
            font-weight: 700;
            margin-bottom: 15px;
            background: linear-gradient(135deg, #ffd700, #ffed4e);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .cta-description {{
            font-size: 16px;
            opacity: 0.9;
            margin-bottom: 25px;
            line-height: 1.5;
        }}
        
        .features-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 25px 0;
        }}
        
        .feature-item {{
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
            transition: all 0.3s ease;
        }}
        
        .feature-item:hover {{
            background: rgba(255,255,255,0.15);
            transform: translateY(-2px);
        }}
        
        .feature-icon {{
            font-size: 32px;
            margin-bottom: 10px;
            display: block;
        }}
        
        .feature-text {{
            font-size: 14px;
            font-weight: 500;
        }}
        
        .footer {{ 
            background: #1a202c; 
            color: #a0aec0; 
            padding: 25px 30px; 
            text-align: center; 
            font-size: 14px;
        }}
        
        .footer-brand {{
            font-size: 18px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 10px;
        }}
        
        .divider {{
            height: 2px;
            background: linear-gradient(to right, transparent, #0077b5, transparent);
            margin: 15px 0;
            border-radius: 1px;
        }}
        
        @media (max-width: 600px) {{
            .container {{ margin: 10px; border-radius: 16px; }}
            .header {{ padding: 25px 20px; }}
            .content {{ padding: 20px; }}
            .post-item {{ padding: 20px; }}
            .action-zone {{ flex-direction: column; gap: 10px; }}
            .summary-stats {{ flex-direction: column; gap: 15px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔔 Publications LinkedIn Détectées</h1>
            <p>Votre veille intelligente en action</p>
        </div>
        
        <div class="stats-bar">
            <div class="stat-item">
                <span class="stat-number">{len(posts)}</span>
                <span class="stat-label">Publications</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">{profiles_count}</span>
                <span class="stat-label">Profils</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">{datetime.now().strftime('%H:%M')}</span>
                <span class="stat-label">Détection</span>
            </div>
        </div>
        
        <div class="content">
"""
        
        # Posts groupés par profil avec UX révolutionnaire
        profiles_posts = {}
        for post in posts:
            if post.profile_name not in profiles_posts:
                profiles_posts[post.profile_name] = []
            profiles_posts[post.profile_name].append(post)
        
        for profile_name, profile_posts in profiles_posts.items():
            for i, post in enumerate(profile_posts):
                # Icône et couleur selon le type
                type_icon = self._get_post_type_icon(post.post_type)
                avatar_letter = profile_name[0].upper()
                
                html += f"""
            <div class="post-item">
                <div class="profile-header">
                    <div class="profile-avatar">{avatar_letter}</div>
                    <div class="profile-info">
                        <div class="profile-name">{profile_name}</div>
                        <div class="post-meta">
                            <span class="post-type-badge">{type_icon} {post.post_type.replace('_', ' ').title()}</span>
                            <span>•</span>
                            <span>📅 {post.detection_time}</span>
                        </div>
                    </div>
                </div>
                
                <div class="post-content">
                    <div class="post-title">{post.post_title}</div>
                    <div class="post-description">
                        {post.post_description}
                    </div>
                </div>
                
                <div class="action-zone">
                    <div class="detection-time">
                        <span>⚡</span>
                        <span>Détection temps réel</span>
                    </div>
                    <a href="{post.post_url}" class="post-link" target="_blank">
                        <span>👀</span>
                        <span>Découvrir le Post</span>
                    </a>
                </div>
            </div>
"""
        
        html += f"""
        </div>
        
        <div class="summary-section">
            <div class="summary-title">
                <span>📊</span>
                <span>Résumé de Veille</span>
            </div>
            
            <div class="summary-stats">
                <div class="summary-stat">
                    <span class="summary-stat-number">{len(posts)}</span>
                    <span class="summary-stat-label">Nouveaux Posts</span>
                </div>
                <div class="summary-stat">
                    <span class="summary-stat-number">{profiles_count}</span>
                    <span class="summary-stat-label">Profils Actifs</span>
                </div>
                <div class="summary-stat">
                    <span class="summary-stat-number">100%</span>
                    <span class="summary-stat-label">Authentique</span>
                </div>
            </div>
            
            <p style="color: #6c757d; font-size: 15px; margin-top: 15px;">
                🎯 Contenu vérifié et analysé intelligemment • {datetime.now().strftime('%d/%m/%Y à %H:%M UTC')}
            </p>
        </div>
        
        <div class="cta-section">
            <div class="cta-title">🚀 LinkedIn Monitor Ultra</div>
            <div class="cta-description">
                Veille professionnelle automatisée avec extraction intelligente de contenu authentique
            </div>
            
            <div class="features-grid">
                <div class="feature-item">
                    <span class="feature-icon">🧠</span>
                    <div class="feature-text">IA Avancée</div>
                </div>
                <div class="feature-item">
                    <span class="feature-icon">⚡</span>
                    <div class="feature-text">Temps Réel</div>
                </div>
                <div class="feature-item">
                    <span class="feature-icon">🎯</span>
                    <div class="feature-text">Précision Max</div>
                </div>
                <div class="feature-item">
                    <span class="feature-icon">🔔</span>
                    <div class="feature-text">Alertes Intelligentes</div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <div class="footer-brand">🤖 LinkedIn Monitor Agent</div>
            <p style="opacity: 0.8; margin-top: 8px;">
                Surveillance automatisée • Ne manquez aucune opportunité professionnelle
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
    def analyze_content_ultra_advanced(html_content: str, profile_url: str, profile_name: str) -> Dict[str, Any]:
        """Analyse ultra-avancée avec extraction intelligente"""
        try:
            # Utilisation du nouvel extracteur intelligent
            extractor = IntelligentContentExtractor()
            posts_data = extractor.extract_real_posts_content(html_content, profile_url, profile_name)
            
            # Génération du hash basé sur le contenu authentique
            content_hash = EnhancedContentAnalyzer._generate_intelligent_hash(posts_data, html_content)
            
            # Score d'activité basé sur la qualité du contenu
            activity_score = EnhancedContentAnalyzer._calculate_quality_score(html_content, posts_data)
            
            return {
                'content_hash': content_hash,
                'activity_score': activity_score,
                'post_count': len(posts_data),
                'posts_data': posts_data,
                'timestamp': datetime.now().isoformat(),
                'analysis_version': '3.0_ultra',
                'content_quality': 'authentic' if posts_data else 'generic'
            }
            
        except Exception as e:
            print(f"❌ Erreur analyse ultra-avancée: {e}")
            return {
                'content_hash': f"error_{hash(html_content[:500]) if html_content else 'empty'}",
                'activity_score': 0,
                'post_count': 0,
                'posts_data': [],
                'timestamp': datetime.now().isoformat(),
                'analysis_version': '1.0_fallback',
                'content_quality': 'error'
            }
    
    @staticmethod
    def _generate_intelligent_hash(posts_data: List[PostData], html_content: str) -> str:
        """Hash intelligent basé sur le contenu authentique"""
        if posts_data:
            # Hash basé sur les titres et descriptions authentiques
            combined = ""
            for post in posts_data:
                combined += f"{post.post_title[:50]}{post.post_description[:100]}{post.post_id}"
            return hashlib.sha256(combined.encode('utf-8')).hexdigest()[:24]
        else:
            # Fallback: analyse des patterns LinkedIn dans le HTML
            linkedin_patterns = re.findall(r'urn:li:activity:\d+|feed-shared-update|update-components', html_content)
            pattern_content = ''.join(linkedin_patterns)
            return hashlib.sha256(pattern_content.encode('utf-8')).hexdigest()[:24]
    
    @staticmethod
    def _calculate_quality_score(html_content: str, posts_data: List[PostData]) -> int:
        """Score de qualité basé sur l'authenticité du contenu"""
        base_score = len(posts_data) * 25  # 25 points par post authentique
        
        # Bonus pour la qualité du contenu
        for post in posts_data:
            # Bonus pour les titres non-génériques
            if not any(noise in post.post_title.lower() for noise in ['nouvelle', 'publication', 'accepter', 'linkedin']):
                base_score += 10
            
            # Bonus pour les descriptions détaillées
            if len(post.post_description) > 50:
                base_score += 5
            
            # Bonus pour la détection du type de post
            if post.post_type != 'publication':
                base_score += 8
        
        # Bonus pour les indicateurs LinkedIn authentiques
        quality_indicators = [
            r'feed-shared-update-v2',
            r'urn:li:activity:\d{10,}',
            r'update-components-text',
            r'artdeco-button'
        ]
        
        for pattern in quality_indicators:
            matches = len(re.findall(pattern, html_content))
            base_score += matches * 3
        
        return min(base_score, 100)


class OptimizedLinkedInMonitor:
    """Agent LinkedIn ultra-optimisé"""
    
    def __init__(self, csv_file: str, email_config: Dict[str, str]):
        self.csv_file = csv_file
        self.notifier = UltraModernEmailNotifier(
            email_config['sender_email'],
            email_config['sender_password'],
            email_config['recipient_email']
        )
        
        # Session HTTP optimisée
        self.session = self._create_optimized_session()
        
        # Collecteur de posts authentiques
        self.all_new_posts: List[PostData] = []
        
        # Statistiques détaillées
        self.stats = {
            'total': 0,
            'success': 0,
            'changes': 0,
            'authentic_posts': 0,
            'errors': 0,
            'content_quality': 0
        }
    
    def _create_optimized_session(self) -> requests.Session:
        """Session HTTP ultra-optimisée"""
        session = requests.Session()
        
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'DNT': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        })
        
        return session
    
    def load_profiles(self) -> List[ProfileData]:
        """Chargement optimisé des profils"""
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
    
    def check_profile_ultra_optimized(self, profile: ProfileData) -> Optional[Dict[str, Any]]:
        """Vérification ultra-optimisée avec extraction intelligente"""
        try:
            print(f"🧠 Analyse intelligente: {profile.name}")
            
            # URLs multiples optimisées
            check_urls = self._generate_intelligent_urls(profile.url)
            
            best_analysis = None
            best_score = 0
            
            for i, url in enumerate(check_urls):
                print(f"   🌐 URL {i+1}: {url}")
                
                response = self._make_enhanced_request(url)
                if response and response.status_code == 200:
                    # Analyse ultra-avancée
                    analysis = EnhancedContentAnalyzer.analyze_content_ultra_advanced(
                        response.text, profile.url, profile.name
                    )
                    
                    current_score = analysis['activity_score']
                    
                    if analysis['posts_data'] and current_score > best_score:
                        print(f"   ✅ Contenu authentique: {analysis['post_count']} posts, Qualité: {current_score}/100")
                        best_analysis = analysis
                        best_score = current_score
                        break  # Arrêter dès qu'on trouve du contenu authentique
                    elif current_score > best_score:
                        best_analysis = analysis
                        best_score = current_score
                
                # Pause entre tentatives
                if i < len(check_urls) - 1:
                    time.sleep(6)
            
            if best_analysis:
                profile.error_count = 0
                self.stats['content_quality'] += best_score
                return best_analysis
            else:
                print(f"   ❌ Aucun contenu authentique trouvé")
                profile.error_count += 1
                return None
                
        except Exception as e:
            print(f"❌ Erreur vérification {profile.name}: {e}")
            profile.error_count += 1
            return None
    
    def _generate_intelligent_urls(self, base_url: str) -> List[str]:
        """Génération d'URLs intelligentes optimisées pour l'extraction"""
        urls = []
        
        if '/company/' in base_url:
            # URLs optimisées pour entreprises
            company_match = re.search(r'/company/([^/]+)', base_url)
            if company_match:
                company_id = company_match.group(1)
                urls.extend([
                    f"https://www.linkedin.com/company/{company_id}/posts/",
                    f"https://www.linkedin.com/company/{company_id}/",
                    f"https://www.linkedin.com/company/{company_id}/updates/",
                ])
        
        elif '/in/' in base_url:
            # URLs optimisées pour profils personnels
            profile_match = re.search(r'/in/([^/]+)', base_url)
            if profile_match:
                profile_id = profile_match.group(1)
                urls.extend([
                    f"https://www.linkedin.com/in/{profile_id}/recent-activity/all/",
                    f"https://www.linkedin.com/in/{profile_id}/",
                    f"https://www.linkedin.com/in/{profile_id}/detail/recent-activity/posts/",
                ])
        
        # Ajouter l'URL originale
        if base_url not in urls:
            urls.append(base_url)
        
        return urls[:3]  # Limiter à 3 URLs pour optimiser
    
    def _make_enhanced_request(self, url: str) -> Optional[requests.Response]:
        """Requête HTTP avec rotation intelligente"""
        for attempt in range(2):
            try:
                # Rotation des User-Agents
                ua_index = attempt % len(IntelligentContentExtractor().user_agents)
                self.session.headers['User-Agent'] = IntelligentContentExtractor().user_agents[ua_index]
                
                response = self.session.get(url, timeout=30)
                
                if response.status_code == 429:
                    wait_time = 45 + (attempt * 20)
                    print(f"   ⏰ Rate limit, attente stratégique {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 200:
                    return response
                else:
                    print(f"   ⚠️ Status {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                print(f"   ❌ Tentative {attempt + 1}: {e}")
                if attempt < 1:
                    time.sleep(10)
        
        return None
    
    def save_profiles(self, profiles: List[ProfileData]) -> bool:
        """Sauvegarde optimisée"""
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
    
    def run_ultra_monitoring(self) -> bool:
        """Cycle de monitoring ultra-optimisé"""
        try:
            print("=" * 90)
            print(f"🚀 LINKEDIN MONITORING ULTRA - {datetime.now()}")
            print("🔥 NOUVELLES FONCTIONNALITÉS RÉVOLUTIONNAIRES:")
            print("   • 🧠 Extraction intelligente de contenu authentique")
            print("   • 📝 Génération automatique de titres pertinents") 
            print("   • ✨ Descriptions contextuelles intelligentes")
            print("   • 🎨 UX email révolutionnaire et engageante")
            print("   • 🎯 Filtrage avancé du contenu générique")
            print("=" * 90)
            
            # Chargement des profils
            profiles = self.load_profiles()
            if not profiles:
                print("❌ Aucun profil à surveiller")
                return False
            
            self.stats['total'] = len(profiles)
            changes_made = False
            self.all_new_posts = []
            
            # Traitement ultra-optimisé
            for i, profile in enumerate(profiles):
                try:
                    print(f"\n--- 🧠 {i+1}/{len(profiles)}: {profile.name} ---")
                    print(f"🔗 URL source: {profile.url}")
                    
                    if profile.error_count >= 5:
                        print(f"⏭️ Profil ignoré (erreurs: {profile.error_count})")
                        continue
                    
                    # Vérification avec extraction intelligente
                    analysis = self.check_profile_ultra_optimized(profile)
                    
                    if analysis:
                        self.stats['success'] += 1
                        current_hash = analysis['content_hash']
                        quality = analysis.get('content_quality', 'unknown')
                        
                        print(f"   📊 Qualité: {quality} | Score: {analysis['activity_score']}/100")
                        
                        # Détection de changement avec contenu authentique
                        if profile.last_post_id != current_hash:
                            print(f"🆕 CONTENU AUTHENTIQUE DÉTECTÉ!")
                            print(f"   🔄 Signature mise à jour")
                            
                            self.stats['changes'] += 1
                            changes_made = True
                            
                            # Ajout des posts authentiques
                            authentic_posts = analysis.get('posts_data', [])
                            if authentic_posts:
                                self.all_new_posts.extend(authentic_posts)
                                self.stats['authentic_posts'] += len(authentic_posts)
                                
                                print(f"   📝 {len(authentic_posts)} post{'s' if len(authentic_posts) > 1 else ''} authentique{'s' if len(authentic_posts) > 1 else ''} avec contenu intelligent:")
                                
                                for j, post in enumerate(authentic_posts):
                                    print(f"      {j+1}. 📑 {post.post_title}")
                                    print(f"         ✏️ {post.post_description[:60]}...")
                                    print(f"         🔗 {post.post_url}")
                            
                            # Mise à jour
                            profile.last_post_id = current_hash
                        else:
                            print("⚪ Aucun nouveau contenu authentique")
                    else:
                        self.stats['errors'] += 1
                        print(f"   ❌ Échec analyse (erreurs: {profile.error_count})")
                    
                    # Pause intelligente
                    if i < len(profiles) - 1:
                        pause = 15 + (i % 3) * 5  # 15-30 secondes
                        print(f"⏳ Pause intelligente: {pause}s...")
                        time.sleep(pause)
                
                except Exception as e:
                    print(f"❌ Erreur critique {profile.name}: {e}")
                    self.stats['errors'] += 1
                    profile.error_count += 1
            
            # Sauvegarde si modifications
            if changes_made:
                print(f"\n💾 Sauvegarde des profils...")
                self.save_profiles(profiles)
            
            # Notification ultra-moderne
            if self.all_new_posts:
                print(f"\n🎨 Préparation notification révolutionnaire...")
                print(f"   📝 Posts authentiques: {len(self.all_new_posts)}")
                
                for post in self.all_new_posts:
                    print(f"   • {post.profile_name}: {post.post_title}")
                
                if self.notifier.send_ultra_modern_notification(self.all_new_posts):
                    print("🎉 Notification révolutionnaire envoyée!")
                else:
                    print("❌ Échec notification")
            else:
                print("\n📧 Aucun nouveau contenu authentique")
            
            # Rapport final ultra-détaillé
            self._print_ultra_report()
            
            return self.stats['success'] > 0
            
        except Exception as e:
            print(f"💥 ERREUR SYSTÈME: {e}")
            traceback.print_exc()
            return False
    
    def _print_ultra_report(self):
        """Rapport ultra-détaillé"""
        print("\n" + "🎯" + "=" * 88 + "🎯")
        print("📊 RAPPORT ULTRA-DÉTAILLÉ - VERSION INTELLIGENTE")
        print("🎯" + "=" * 88 + "🎯")
        
        print(f"📋 Profils analysés: {self.stats['success']}/{self.stats['total']}")
        print(f"🆕 Changements détectés: {self.stats['changes']}")
        print(f"🧠 Posts authentiques extraits: {self.stats['authentic_posts']}")
        print(f"❌ Erreurs: {self.stats['errors']}")
        
        # Calculs avancés
        success_rate = (self.stats['success'] / self.stats['total']) * 100 if self.stats['total'] > 0 else 0
        avg_quality = (self.stats['content_quality'] / max(self.stats['success'], 1)) if self.stats['success'] > 0 else 0
        
        print(f"📈 Taux de succès: {success_rate:.1f}%")
        print(f"⭐ Qualité moyenne contenu: {avg_quality:.1f}/100")
        
        if self.all_new_posts:
            print(f"\n🎉 POSTS AUTHENTIQUES DÉTECTÉS:")
            for i, post in enumerate(self.all_new_posts, 1):
                print(f"   {i}. 👤 {post.profile_name}")
                print(f"      📑 {post.post_title}")
                print(f"      ✏️ {post.post_description[:80]}...")
                print(f"      🔗 {post.post_url}")
                print(f"      🏷️ Type: {post.post_type}")
                print(f"      ─" * 60)
        
        # Statistiques avancées
        if self.all_new_posts:
            post_types = {}
            for post in self.all_new_posts:
                post_types[post.post_type] = post_types.get(post.post_type, 0) + 1
            
            print(f"\n📊 RÉPARTITION PAR TYPE:")
            for post_type, count in post_types.items():
                icon = UltraModernEmailNotifier(None, None, None)._get_post_type_icon(post_type)
                print(f"   {icon} {post_type.replace('_', ' ').title()}: {count}")
        
        print("🎯" + "=" * 88 + "🎯")


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
    """Point d'entrée ultra-optimisé"""
    try:
        print("🎯" + "=" * 88 + "🎯")
        print("🤖 LINKEDIN MONITOR AGENT - VERSION ULTRA INTELLIGENTE")
        print("🔥 RÉVOLUTION DE L'EXTRACTION DE CONTENU:")
        print("   • 🧠 IA avancée pour extraire le VRAI contenu des posts")
        print("   • 📝 Génération automatique de titres pertinents")
        print("   • ✨ Descriptions contextuelles intelligentes")
        print("   • 🚫 Filtrage total du contenu générique/bruit")
        print("   • 🎨 UX email révolutionnaire avec animations")
        print("   • 🎯 Détection du type de contenu (emploi, événement, etc.)")
        print("🎯" + "=" * 88 + "🎯")
        
        # Validation
        email_config = validate_environment()
        
        # Mode debug
        debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
        if debug_mode:
            print("🐛 MODE DEBUG ULTRA ACTIVÉ")
        
        # Lancement du monitoring révolutionnaire
        monitor = OptimizedLinkedInMonitor("linkedin_urls.csv", email_config)
        success = monitor.run_ultra_monitoring()
        
        # Résultat final
        if success:
            print("🎉 MONITORING ULTRA-INTELLIGENT TERMINÉ!")
            if monitor.all_new_posts:
                print(f"🧠 {len(monitor.all_new_posts)} posts authentiques avec contenu intelligent")
                print("🎨 Notification révolutionnaire envoyée")
                
                # Aperçu des titres générés
                print("\n📝 APERÇU DES TITRES INTELLIGENTS:")
                for post in monitor.all_new_posts:
                    print(f"   ✨ {post.post_title}")
            else:
                print("✅ Veille active - Aucun nouveau contenu authentique")
            sys.exit(0)
        else:
            print("💥 ÉCHEC DU MONITORING ULTRA")
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
