"""
🤖 AI-POWERED ANALYSIS MODULE
Advanced behavioral analysis, content filtering, and risk scoring
"""
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import re

# Optional imports - graceful degradation
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ scikit-learn not available. Some ML features disabled.")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("⚠️ opencv-python not available. Image analysis disabled.")

try:
    from transformers import pipeline
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("⚠️ transformers/torch not available. Advanced NLP features disabled.")

class AIAnalysisEngine:
    def __init__(self):
        self.sentiment_analyzer = None
        self.image_classifier = None
        self.behavior_model = None
        
        # Initialize models (lazy loading)
        self.risk_scores = defaultdict(float)
        self.behavior_patterns = defaultdict(list)
        
    def initialize_models(self):
        """Initialize AI models (call once at startup)"""
        try:
            if TRANSFORMERS_AVAILABLE:
                # Sentiment Analysis
                self.sentiment_analyzer = pipeline("sentiment-analysis", 
                                                  model="distilbert-base-uncased-finetuned-sst-2-english")
                
                # Image Classification for content moderation
                # self.image_classifier = pipeline("image-classification")
                
                print("✅ AI Models initialized")
            else:
                print("ℹ️ AI Models disabled - transformers not available")
        except Exception as e:
            print(f"⚠️ AI Models initialization failed: {e}")
    
    # ============ CONTENT ANALYSIS ============
    
    def analyze_screenshot_content(self, image_data):
        """
        Analyze screenshot for inappropriate content
        Returns: risk_score (0-100), detected_issues[]
        """
        if not CV2_AVAILABLE:
            return {'risk_score': 0, 'issues': ['Image analysis unavailable']}
        
        try:
            # Decode image
            import base64
            img_bytes = base64.b64decode(image_data)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            issues = []
            risk_score = 0
            
            # 1. Skin tone detection (basic NSFW check)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            lower_skin = np.array([0, 20, 70], dtype=np.uint8)
            upper_skin = np.array([20, 255, 255], dtype=np.uint8)
            mask = cv2.inRange(hsv, lower_skin, upper_skin)
            skin_ratio = np.sum(mask > 0) / mask.size
            
            if skin_ratio > 0.4:  # More than 40% skin tones
                issues.append("High skin tone detected")
                risk_score += 30
            
            # 2. Text detection in screenshot (OCR)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Use pytesseract if available
            try:
                import pytesseract
                text = pytesseract.image_to_string(gray)
                
                # Check for inappropriate keywords
                bad_keywords = ['porn', 'xxx', 'sex', 'drugs', 'hack', 'cheat']
                for keyword in bad_keywords:
                    if keyword in text.lower():
                        issues.append(f"Keyword detected: {keyword}")
                        risk_score += 20
            except:
                pass
            
            # 3. Dominant color analysis
            dominant_color = self._get_dominant_color(img)
            if dominant_color == 'red':  # Red often indicates warnings/adult content
                risk_score += 10
            
            return {
                'risk_score': min(risk_score, 100),
                'issues': issues,
                'timestamp': datetime.now().timestamp()
            }
            
        except Exception as e:
            print(f"Screenshot analysis error: {e}")
            return {'risk_score': 0, 'issues': []}
    if not SKLEARN_AVAILABLE:
            return 'unknown'
        
        
    def _get_dominant_color(self, img):
        """Get dominant color from image"""
        try:
            pixels = img.reshape(-1, 3)
            kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
            kmeans.fit(pixels)
            
            dominant = kmeans.cluster_centers_[0]
            
            # Classify color
            if dominant[2] > 150 and dominant[0] < 100:  # High red, low blue
                return 'red'
            return 'unknown'
        except:
            return 'unknown'
    
    # ============ TYPING BEHAVIOR ANALYSIS ============
    
    def analyze_keystroke_sentiment(self, keystroke_data):
        """
        Analyze typing sentiment and mood
        Returns: sentiment (positive/negative), confidence, mood
        """
        if not self.sentiment_analyzer:
            return {'sentiment': 'unknown', 'confidence': 0}
        
        try:
            # Extract text from keystroke data
            if isinstance(keystroke_data, list):
                text = ''.join([k.get('key', '') for k in keystroke_data if k.get('key')])
            else:
                text = str(keystroke_data)
            
            # Clean text
            text = text.replace('[', '').replace(']', '').strip()
            
            if len(text) < 10:
                return {'sentiment': 'insufficient_data', 'confidence': 0}
            
            # Analyze sentiment
            result = self.sentiment_analyzer(text[:512])[0]
            
            # Classify mood
            mood = self._classify_mood(text, result['label'])
            
            return {
                'sentiment': result['label'],
                'confidence': result['score'],
                'mood': mood,
                'text_sample': text[:100]
            }
            
        except Exception as e:
            print(f"Sentiment analysis error: {e}")
            return {'sentiment': 'error', 'confidence': 0}
    
    def _classify_mood(self, text, sentiment):
        """Classify detailed mood from text"""
        text_lower = text.lower()
        
        # Anger indicators
        anger_words = ['hate', 'angry', 'mad', 'furious', 'damn', 'stupid']
        if any(word in text_lower for word in anger_words):
            return 'angry'
        
        # Sadness indicators
        sad_words = ['sad', 'depressed', 'lonely', 'cry', 'hurt']
        if any(word in text_lower for word in sad_words):
            return 'sad'
        
        # Anxiety indicators
        anxiety_words = ['worry', 'anxious', 'scared', 'afraid', 'nervous']
        if any(word in text_lower for word in anxiety_words):
            return 'anxious'
        
        # Default to sentiment
        return 'positive' if sentiment == 'POSITIVE' else 'negative'
    
    # ============ BEHAVIOR PATTERN ANALYSIS ============
    
    def analyze_app_usage_patterns(self, app_usage_history):
        """
        Detect anomalies in app usage patterns
        Returns: anomalies[], risk_score, insights[]
        """
        try:
            anomalies = []
            risk_score = 0
            insights = []
            
            # Calculate average usage
            total_apps = len(app_usage_history)
            if total_apps == 0:
                return {'anomalies': [], 'risk_score': 0, 'insights': []}
            
            app_times = {}
            for usage in app_usage_history:
                if isinstance(usage, dict) and 'usage' in usage:
                    for app_data in usage['usage']:
                        app_name, time_spent = app_data[0], app_data[1]
                        if app_name not in app_times:
                            app_times[app_name] = []
                        app_times[app_name].append(time_spent)
            
            # Detect anomalies
            for app_name, times in app_times.items():
                avg_time = np.mean(times)
                std_time = np.std(times)
                
                # Check for sudden spikes
                if len(times) > 1:
                    latest_time = times[-1]
                    if latest_time > avg_time + (2 * std_time):
                        anomalies.append({
                            'app': app_name,
                            'type': 'sudden_increase',
                            'value': latest_time,
                            'expected': avg_time
                        })
                        risk_score += 15
                
                # Check for gaming/social media overuse
                gaming_keywords = ['game', 'minecraft', 'fortnite', 'roblox']
                social_keywords = ['discord', 'whatsapp', 'instagram', 'tiktok']
                
                if any(kw in app_name.lower() for kw in gaming_keywords):
                    if avg_time > 3600:  # More than 1 hour average
                        insights.append(f"High gaming usage: {app_name} ({avg_time/3600:.1f}h avg)")
                        risk_score += 10
                
                if any(kw in app_name.lower() for kw in social_keywords):
                    if avg_time > 1800:  # More than 30 minutes average
                        insights.append(f"High social media usage: {app_name} ({avg_time/60:.0f}m avg)")
                        risk_score += 10
            
            return {
                'anomalies': anomalies,
                'risk_score': min(risk_score, 100),
                'insights': insights
            }
            
        except Exception as e:
            print(f"App usage analysis error: {e}")
            return {'anomalies': [], 'risk_score': 0, 'insights': []}
    
    def detect_time_pattern_anomalies(self, activity_timestamps):
        """
        Detect unusual activity patterns (e.g., late night usage)
        """
        try:
            anomalies = []
            
            for timestamp in activity_timestamps:
                dt = datetime.fromtimestamp(timestamp)
                hour = dt.hour
                
                # Late night usage (11 PM - 5 AM)
                if hour >= 23 or hour <= 5:
                    anomalies.append({
                        'type': 'late_night_activity',
                        'time': dt.strftime('%Y-%m-%d %H:%M:%S'),
                        'risk': 'medium'
                    })
                
                # School hours usage (9 AM - 3 PM on weekdays)
                if dt.weekday() < 5 and 9 <= hour <= 15:
                    anomalies.append({
                        'type': 'school_hours_activity',
                        'time': dt.strftime('%Y-%m-%d %H:%M:%S'),
                        'risk': 'high'
                    })
            
            return anomalies
            
        except Exception as e:
            print(f"Time pattern analysis error: {e}")
            return []
    
    # ============ WEBSITE CONTENT ANALYSIS ============
    
    def analyze_website_risk(self, url):
        """
        Analyze website URL for risk factors
        Returns: risk_level, category, reason
        """
        try:
            url_lower = url.lower()
            
            # Adult content indicators
            adult_keywords = ['porn', 'xxx', 'sex', 'adult', 'nude', 'nsfw']
            if any(kw in url_lower for kw in adult_keywords):
                return {
                    'risk_level': 'critical',
                    'category': 'adult_content',
                    'reason': 'Adult content detected in URL'
                }
            
            # Gambling
            gambling_keywords = ['casino', 'bet', 'poker', 'gambling']
            if any(kw in url_lower for kw in gambling_keywords):
                return {
                    'risk_level': 'high',
                    'category': 'gambling',
                    'reason': 'Gambling site detected'
                }
            
            # Violence/weapons
            violence_keywords = ['weapon', 'gun', 'bomb', 'violence']
            if any(kw in url_lower for kw in violence_keywords):
                return {
                    'risk_level': 'high',
                    'category': 'violence',
                    'reason': 'Violence-related content'
                }
            
            # Hacking/illegal
            illegal_keywords = ['hack', 'crack', 'pirate', 'torrent', 'illegal']
            if any(kw in url_lower for kw in illegal_keywords):
                return {
                    'risk_level': 'high',
                    'category': 'illegal',
                    'reason': 'Potentially illegal content'
                }
            
            # Social media (medium risk for young users)
            social_domains = ['facebook.com', 'instagram.com', 'tiktok.com', 'snapchat.com']
            if any(domain in url_lower for domain in social_domains):
                return {
                    'risk_level': 'medium',
                    'category': 'social_media',
                    'reason': 'Social media platform'
                }
            
            # Gaming
            gaming_domains = ['steam', 'epicgames', 'roblox.com', 'minecraft']
            if any(domain in url_lower for domain in gaming_domains):
                return {
                    'risk_level': 'low',
                    'category': 'gaming',
                    'reason': 'Gaming platform'
                }
            
            return {
                'risk_level': 'safe',
                'category': 'general',
                'reason': 'No risk indicators found'
            }
            
        except Exception as e:
            return {'risk_level': 'unknown', 'category': 'error', 'reason': str(e)}
    
    # ============ COMPREHENSIVE RISK SCORING ============
    
    def calculate_overall_risk_score(self, pc_data):
        """
        Calculate comprehensive risk score (0-100) based on all factors
        Returns: risk_score, risk_level, contributing_factors[]
        """
        try:
            total_score = 0
            factors = []
            
            # 1. Keyword alerts
            if 'keyword_alerts' in pc_data and pc_data['keyword_alerts']:
                keyword_score = len(pc_data['keyword_alerts']) * 15
                total_score += keyword_score
                factors.append({
                    'factor': 'Keyword Alerts',
                    'score': keyword_score,
                    'details': f"{len(pc_data['keyword_alerts'])} alerts"
                })
            
            # 2. Screenshot content
            if 'screenshot_analysis' in pc_data:
                screenshot_score = pc_data['screenshot_analysis'].get('risk_score', 0)
                total_score += screenshot_score * 0.3  # Weight: 30%
                factors.append({
                    'factor': 'Screenshot Content',
                    'score': screenshot_score,
                    'details': pc_data['screenshot_analysis'].get('issues', [])
                })
            
            # 3. App usage patterns
            if 'app_usage_analysis' in pc_data:
                app_score = pc_data['app_usage_analysis'].get('risk_score', 0)
                total_score += app_score * 0.2  # Weight: 20%
                factors.append({
                    'factor': 'App Usage Patterns',
                    'score': app_score,
                    'details': pc_data['app_usage_analysis'].get('insights', [])
                })
            
            # 4. Time pattern anomalies
            if 'time_anomalies' in pc_data and pc_data['time_anomalies']:
                time_score = len(pc_data['time_anomalies']) * 10
                total_score += time_score
                factors.append({
                    'factor': 'Unusual Activity Times',
                    'score': time_score,
                    'details': f"{len(pc_data['time_anomalies'])} anomalies"
                })
            
            # 5. Blocked attempts
            if 'blocked_attempts' in pc_data:
                blocked_score = pc_data['blocked_attempts'] * 5
                total_score += blocked_score
                factors.append({
                    'factor': 'Blocked Attempts',
                    'score': blocked_score,
                    'details': f"{pc_data['blocked_attempts']} attempts"
                })
            
            # 6. Geofence violations
            if 'geofence_violations' in pc_data:
                geo_score = pc_data['geofence_violations'] * 20
                total_score += geo_score
                factors.append({
                    'factor': 'Location Violations',
                    'score': geo_score,
                    'details': f"{pc_data['geofence_violations']} violations"
                })
            
            # Normalize to 0-100
            risk_score = min(total_score, 100)
            
            # Determine risk level
            if risk_score >= 70:
                risk_level = 'critical'
            elif risk_score >= 50:
                risk_level = 'high'
            elif risk_score >= 30:
                risk_level = 'medium'
            elif risk_score >= 10:
                risk_level = 'low'
            else:
                risk_level = 'minimal'
            
            return {
                'risk_score': risk_score,
                'risk_level': risk_level,
                'contributing_factors': factors,
                'timestamp': datetime.now().timestamp()
            }
            
        except Exception as e:
            print(f"Risk calculation error: {e}")
            return {
                'risk_score': 0,
                'risk_level': 'unknown',
                'contributing_factors': [],
                'timestamp': datetime.now().timestamp()
            }
    
    # ============ VOICE ANALYSIS (if audio available) ============
    
    def analyze_voice_recording(self, audio_data):
        """
        Analyze voice recording for speaker identification and sentiment
        (Requires speech recognition and speaker diarization models)
        """
        # TODO: Implement with speech recognition libraries
        return {
            'speakers_detected': 1,
            'transcription': '',
            'sentiment': 'unknown'
        }
    
    # ============ PREDICTIVE ANALYSIS ============
    
    def predict_future_behavior(self, historical_data):
        """
        Predict potential risky behavior based on historical patterns
        """
        try:
            predictions = []
            
            # Analyze trends
            if len(historical_data) > 7:  # Need at least a week of data
                # Check for escalating patterns
                recent_scores = [d.get('risk_score', 0) for d in historical_data[-7:]]
                
                if np.mean(recent_scores[-3:]) > np.mean(recent_scores[:3]):
                    predictions.append({
                        'prediction': 'Increasing risk trend detected',
                        'confidence': 0.7,
                        'recommendation': 'Increase monitoring frequency'
                    })
            
            return predictions
            
        except Exception as e:
            print(f"Prediction error: {e}")
            return []

# Singleton instance
ai_engine = AIAnalysisEngine()

# Export functions
def analyze_content(image_data):
    return ai_engine.analyze_screenshot_content(image_data)

def analyze_sentiment(keystroke_data):
    return ai_engine.analyze_keystroke_sentiment(keystroke_data)

def analyze_behavior(app_usage_history):
    return ai_engine.analyze_app_usage_patterns(app_usage_history)

def calculate_risk_score(pc_data):
    return ai_engine.calculate_overall_risk_score(pc_data)

def analyze_website(url):
    return ai_engine.analyze_website_risk(url)
