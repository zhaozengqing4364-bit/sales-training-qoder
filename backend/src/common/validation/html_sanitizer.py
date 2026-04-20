"""
HTML Sanitizer - Prevent XSS attacks

Implements Constitution Principle VI: Data privacy and compliance
- Sanitizes HTML to prevent XSS attacks
- Removes dangerous tags and attributes
- Validates URLs to prevent javascript: protocol

Requirements: P1-FIXES.md Issue #22
"""

import re


class HTMLSanitizer:
    """
    HTML sanitizer for preventing XSS attacks

    Features:
    - Removes dangerous HTML tags
    - Removes dangerous attributes
    - Validates URLs (blocks javascript: protocol)
    - Can strip all HTML for plain text

    Usage:
        # Sanitize HTML content
        safe_html = HTMLSanitizer.sanitize(user_content)

        # Strip all HTML
        plain_text = HTMLSanitizer.sanitize_text(user_content)

        # Validate URL
        safe_url = HTMLSanitizer.validate_url(user_url)
    """

    # Allowed HTML tags (whitelist approach)
    ALLOWED_TAGS: set[str] = {
        "p",
        "br",
        "strong",
        "em",
        "b",
        "i",
        "u",
        "a",
        "ul",
        "ol",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "blockquote",
        "code",
        "pre",
        "span",
        "div",
    }

    # Allowed attributes per tag
    ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
        "a": {"href", "title", "target"},
        "img": {"src", "alt", "title", "width", "height"},
        "*": {"class", "id"},
    }

    # Dangerous tags that should never be allowed
    DANGEROUS_TAGS: set[str] = {
        "script",
        "style",
        "iframe",
        "object",
        "embed",
        "form",
        "input",
        "textarea",
        "button",
        "select",
        "option",
        "link",
        "meta",
        "base",
        "head",
        "body",
        "html",
        "frame",
        "frameset",
        "applet",
        "param",
    }

    # Dangerous attributes that should never be allowed
    DANGEROUS_ATTRIBUTES: set[str] = {
        "onerror",
        "onload",
        "onclick",
        "onmouseover",
        "onmouseout",
        "onfocus",
        "onblur",
        "onchange",
        "onsubmit",
        "onreset",
        "onselect",
        "onkeydown",
        "onkeypress",
        "onkeyup",
        "style",
        "javascript",
        "expression",
    }

    # Allowed URL schemes
    ALLOWED_SCHEMES: set[str] = {"http", "https", "mailto", "tel"}

    @classmethod
    def sanitize(cls, html: str, strip: bool = False) -> str:
        """
        Sanitize HTML by removing dangerous tags and attributes

        Args:
            html: Input HTML string
            strip: If True, remove all HTML tags

        Returns:
            Sanitized HTML string
        """
        if not html:
            return ""

        if strip:
            return cls._strip_all_html(html)

        # Remove dangerous tags
        result = cls._remove_dangerous_tags(html)

        # Remove dangerous attributes
        result = cls._remove_dangerous_attributes(result)

        # Validate URLs in attributes
        result = cls._validate_urls(result)

        return result

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """
        Strip all HTML tags, return plain text

        Args:
            text: Input text that may contain HTML

        Returns:
            Plain text with HTML removed
        """
        return cls._strip_all_html(text)

    @classmethod
    def validate_url(cls, url: str) -> str | None:
        """
        Validate URL to prevent javascript: protocol attacks

        Args:
            url: URL to validate

        Returns:
            Validated URL or None if invalid
        """
        if not url:
            return None

        url = url.strip()

        # Check for javascript: protocol (case insensitive)
        if re.match(r"^javascript:", url, re.IGNORECASE):
            return None

        # Check for data: URI with script
        if re.match(r"^data:text/html", url, re.IGNORECASE):
            return None

        # Check for vbscript: protocol
        if re.match(r"^vbscript:", url, re.IGNORECASE):
            return None

        # Check scheme
        scheme_match = re.match(r"^([a-z][a-z0-9+.-]*):", url, re.IGNORECASE)
        if scheme_match:
            scheme = scheme_match.group(1).lower()
            if scheme not in cls.ALLOWED_SCHEMES:
                return None

        return url

    @classmethod
    def _strip_all_html(cls, html: str) -> str:
        """Remove all HTML tags"""
        # Remove script and style content first
        html = re.sub(
            r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
        )
        html = re.sub(
            r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE
        )

        # Remove all HTML tags
        html = re.sub(r"<[^>]+?>", "", html)

        # Decode HTML entities
        html = html.replace("&lt;", "<")
        html = html.replace("&gt;", ">")
        html = html.replace("&amp;", "&")
        html = html.replace("&quot;", '"')
        html = html.replace("&#39;", "'")
        html = html.replace("&nbsp;", " ")

        return html.strip()

    @classmethod
    def _remove_dangerous_tags(cls, html: str) -> str:
        """Remove dangerous HTML tags"""
        result = html

        for tag in cls.DANGEROUS_TAGS:
            # Remove opening tags with content
            pattern = rf"<{tag}[^>]*>.*?</{tag}>"
            result = re.sub(pattern, "", result, flags=re.DOTALL | re.IGNORECASE)

            # Remove self-closing tags
            pattern = rf"<{tag}[^/]*/>"
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)

            # Remove orphaned opening tags
            pattern = rf"<{tag}[^>]*>"
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)

            # Remove orphaned closing tags
            pattern = rf"</{tag}>"
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)

        return result

    @classmethod
    def _remove_dangerous_attributes(cls, html: str) -> str:
        """Remove dangerous attributes from HTML tags"""
        result = html

        for attr in cls.DANGEROUS_ATTRIBUTES:
            # Remove event handlers and dangerous attributes
            pattern = rf'\s{attr}=["\'][^"\']*["\']'
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)

            # Remove without quotes
            pattern = rf"\s{attr}=[^\s>]+"
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)

        return result

    @classmethod
    def _validate_urls(cls, html: str) -> str:
        """Validate URLs in href and src attributes"""

        def replace_url(match):
            attr = match.group(1)
            url = match.group(2)

            validated = cls.validate_url(url)
            if validated is None:
                # Remove the attribute if URL is invalid
                return ""

            return f' {attr}="{validated}"'

        # Validate href attributes
        result = re.sub(
            r'\s(href)=["\']([^"\']+)["\']', replace_url, html, flags=re.IGNORECASE
        )

        # Validate src attributes
        result = re.sub(
            r'\s(src)=["\']([^"\']+)["\']', replace_url, result, flags=re.IGNORECASE
        )

        return result

    @classmethod
    def escape_html(cls, text: str) -> str:
        """
        Escape HTML special characters

        Args:
            text: Plain text to escape

        Returns:
            Escaped text safe for HTML insertion
        """
        if not text:
            return ""

        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )


# Convenience function
def sanitize_html(html: str, strip: bool = False) -> str:
    """Convenience function to sanitize HTML"""
    return HTMLSanitizer.sanitize(html, strip)


def escape_html(text: str) -> str:
    """Convenience function to escape HTML"""
    return HTMLSanitizer.escape_html(text)
