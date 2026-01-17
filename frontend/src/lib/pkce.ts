/**
 * PKCE (Proof Key for Code Exchange) utilities for OAuth
 */

/**
 * Generate a random code verifier for PKCE
 * Must be 43-128 characters as per RFC 7636
 */
export function generateCodeVerifier(): string {
  const array = new Uint8Array(64); // 64 bytes = ~86 chars in base64url
  crypto.getRandomValues(array);
  const verifier = base64UrlEncode(array);
  console.log('[PKCE] Generated code_verifier (length=' + verifier.length + '):', verifier.substring(0, 10) + '...');
  return verifier;
}

/**
 * Generate code challenge from code verifier
 */
export async function generateCodeChallenge(codeVerifier: string): Promise<string> {
  console.log('[PKCE] Generating challenge for verifier:', codeVerifier.substring(0, 10) + '...');

  // Check if crypto.subtle is available (requires secure context: HTTPS or localhost)
  if (!crypto || !crypto.subtle) {
    throw new Error(
      'Web Crypto API not available. Please access this site via HTTPS or localhost (not IP address). ' +
      'Current URL: ' + window.location.href
    );
  }

  const encoder = new TextEncoder();
  const data = encoder.encode(codeVerifier);
  const hash = await crypto.subtle.digest('SHA-256', data);
  const challenge = base64UrlEncode(new Uint8Array(hash));
  console.log('[PKCE] Generated challenge:', challenge.substring(0, 10) + '...');
  return challenge;
}

/**
 * Base64 URL encode (without padding)
 */
function base64UrlEncode(array: Uint8Array): string {
  const base64 = btoa(String.fromCharCode(...array));
  return base64
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}

/**
 * Store code verifier in local storage
 */
export function storeCodeVerifier(codeVerifier: string): void {
  localStorage.setItem('pkce_code_verifier', codeVerifier);
  console.log('[PKCE] Stored code_verifier:', codeVerifier.substring(0, 10) + '...');
}

/**
 * Retrieve and remove code verifier from local storage
 */
export function retrieveCodeVerifier(): string | null {
  const codeVerifier = localStorage.getItem('pkce_code_verifier');
  console.log('[PKCE] Retrieved code_verifier:', codeVerifier ? codeVerifier.substring(0, 10) + '...' : 'null');
  if (codeVerifier) {
    localStorage.removeItem('pkce_code_verifier');
  }
  return codeVerifier;
}
