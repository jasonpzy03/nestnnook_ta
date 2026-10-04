"""Sign-in translations without client-side scripts or changes to login security."""
from html import escape

LANGUAGE_COOKIE = 'nest_language'
TRANSLATIONS = {
    'Team sign in': '团队登录',
    'Nest & Nook tenancy documents': 'Nest & Nook 租赁文件',
    'Team password': '团队密码',
    'Sign in': '登录',
    'Language': '语言',
    'System language': '跟随系统',
    'Auto': '自动',
    'Apply': '应用',
    'Incorrect team password.': '团队密码不正确。',
    'Too many attempts. Try again in 15 minutes.': '尝试次数过多，请在15分钟后重试。',
    'Team access is not configured. Configure the team password on the server.': '尚未配置团队登录，请在服务器上设置团队密码。',
}

def language_for(request):
    preference = request.query_params.get('lang', request.cookies.get(LANGUAGE_COOKIE, 'auto')) if request else 'auto'
    if preference in ('en', 'zh'):
        return preference, preference
    candidates = []
    for position, item in enumerate((request.headers.get('accept-language', '') if request else '').split(',')):
        parts = item.strip().split(';')
        try:
            weight = float(parts[1].strip().removeprefix('q=')) if len(parts) > 1 else 1
        except ValueError:
            continue
        if weight > 0:
            candidates.append((-weight, position, parts[0].lower().split('-')[0]))
    language = next((code for _, _, code in sorted(candidates) if code in ('en', 'zh')), 'en')
    return language, 'auto'

def render_login(html, request, message):
    language, preference = language_for(request)
    def translated(value):
        return escape(TRANSLATIONS.get(value, value) if language == 'zh' else value)
    values = {
        'LANG': 'zh-Hans' if language == 'zh' else 'en',
        'TITLE': translated('Team sign in'), 'SUBTITLE': translated('Nest & Nook tenancy documents'),
        'PASSWORD': translated('Team password'), 'SUBMIT': translated('Sign in'),
        'LANGUAGE': translated('Language'), 'AUTO': translated('Auto'), 'APPLY': translated('Apply'),
        'MESSAGE': translated(message),
        'AUTO_SELECTED': 'selected' if preference == 'auto' else '',
        'EN_SELECTED': 'selected' if preference == 'en' else '',
        'ZH_SELECTED': 'selected' if preference == 'zh' else '',
    }
    for key, value in values.items():
        html = html.replace('<!--'+key+'-->', value)
    return html
