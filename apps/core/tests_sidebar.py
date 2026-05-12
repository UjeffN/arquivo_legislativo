from pathlib import Path
from unittest import TestCase


class PainelSidebarTemplateTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.templates_dir = Path(__file__).resolve().parents[2] / 'templates'
        template_path = cls.templates_dir / 'layouts' / 'painel.html'
        cls.template = template_path.read_text(encoding='utf-8')
        cls.admin_css = (
            Path(__file__).resolve().parents[2] / 'static' / 'css' / 'tailwind-admin.css'
        ).read_text(encoding='utf-8')

    def test_sidebar_collapsed_mode_keeps_only_icons_visible(self):
        collapsed_selector_guard = 'html[data-admin-sidebar-collapsed="true"] .admin-layout'
        self.assertIn(f'{collapsed_selector_guard} .sidebar {{', self.template)
        self.assertIn('width: 5rem;', self.template)
        self.assertIn(f'{collapsed_selector_guard} .main-content', self.template)
        self.assertIn(f'{collapsed_selector_guard} .sidebar-item-label', self.template)
        self.assertIn('opacity: 0;', self.template)
        self.assertIn('width: 0;', self.template)
        self.assertIn('overflow-x: hidden;', self.template)
        self.assertIn('pointer-events: none;', self.template)
        self.assertIn(f'{collapsed_selector_guard} .sidebar-toggle', self.template)
        self.assertIn('border-width: 0;', self.template)
        self.assertIn('<span class="sidebar-item-label">Dashboard</span>', self.template)
        self.assertIn('<span class="sidebar-item-label">Sair</span>', self.template)

    def test_sidebar_toggle_icons_have_reliable_collapsed_and_expanded_states(self):
        self.assertIn('id="sidebarToggle"', self.template)
        self.assertIn('class="sidebar-toggle"', self.template)
        self.assertIn('fa-chevron-left sidebar-toggle-icon sidebar-toggle-icon-collapse', self.template)
        self.assertIn('fa-chevron-right sidebar-toggle-icon sidebar-toggle-icon-expand', self.template)
        self.assertIn('title="Expandir/recolher menu"', self.template)
        self.assertIn('id="admin-sidebar-critical-css"', self.template)
        self.assertLess(
            self.template.index('id="admin-sidebar-critical-css"'),
            self.template.index('<body>')
        )
        self.assertIn('html[data-admin-sidebar-collapsed="false"] .sidebar-toggle-icon-collapse', self.template)
        self.assertIn('html[data-admin-sidebar-collapsed="true"] .sidebar-toggle-icon-expand', self.template)
        self.assertIn('transition: opacity 0.18s ease, transform 0.22s ease;', self.template)
        self.assertNotIn('sidebar-pin-toggle', self.template)
        self.assertNotIn('pin-0.svg', self.template)
        self.assertNotIn('pin-1.svg', self.template)

    def test_collapsed_sidebar_logo_becomes_expand_button_on_hover(self):
        collapsed_selector_guard = 'html[data-admin-sidebar-collapsed="true"] .admin-layout'
        self.assertIn('id="sidebarLogo"', self.template)
        self.assertIn('sidebar-logo-icon sidebar-logo-icon-original', self.template)
        self.assertIn('sidebar-logo-icon sidebar-logo-icon-expand', self.template)
        self.assertIn('fa-chevron-right sidebar-logo-icon sidebar-logo-icon-expand', self.template)
        self.assertIn(f'{collapsed_selector_guard} .sidebar-logo:hover', self.template)
        self.assertIn(f'{collapsed_selector_guard} .sidebar-logo:focus-visible', self.template)
        self.assertIn(f'{collapsed_selector_guard} .sidebar-logo:hover .sidebar-logo-icon-original', self.template)
        self.assertIn(f'{collapsed_selector_guard} .sidebar-logo:hover .sidebar-logo-icon-expand', self.template)
        self.assertIn('cursor: pointer;', self.template)
        self.assertIn("sidebarLogo.setAttribute('aria-label', normalizedCollapsed ? 'Expandir menu' : 'Ir para o dashboard');", self.template)
        self.assertIn("sidebarLogo.setAttribute('title', normalizedCollapsed ? 'Expandir menu' : 'Ir para o dashboard');", self.template)
        self.assertIn("sidebarLogo.addEventListener('click'", self.template)
        self.assertIn("adminLayout.classList.contains('sidebar-collapsed')", self.template)
        self.assertIn('event.preventDefault();', self.template)
        self.assertIn('setSidebarState(false, true);', self.template)

    def test_sidebar_collapse_toggles_and_persists_in_local_storage(self):
        self.assertIn("document.documentElement.classList.add('admin-sidebar-preload');", self.template)
        self.assertIn("var sidebarCollapsedKey = 'sidebarCollapsed';", self.template)
        self.assertIn("sidebarCollapsed = localStorage.getItem(sidebarCollapsedKey) === 'true';", self.template)
        self.assertIn("document.documentElement.setAttribute('data-admin-sidebar-collapsed', String(sidebarCollapsed));", self.template)
        self.assertIn('html.admin-sidebar-preload .sidebar', self.template)
        self.assertIn('html[data-admin-sidebar-collapsed="true"] .admin-layout .sidebar', self.template)
        self.assertIn("const sidebarCollapsedKey = 'sidebarCollapsed';", self.template)
        self.assertIn('function readStoredSidebarCollapsed()', self.template)
        self.assertIn('function persistSidebarState(collapsed)', self.template)
        self.assertIn('function setSidebarState(collapsed, shouldPersist)', self.template)
        self.assertIn("adminLayout.classList.toggle('sidebar-collapsed', normalizedCollapsed);", self.template)
        self.assertIn("document.documentElement.setAttribute('data-admin-sidebar-collapsed', String(normalizedCollapsed));", self.template)
        self.assertIn("sidebarToggle.setAttribute('aria-expanded', String(!normalizedCollapsed));", self.template)
        self.assertIn("localStorage.setItem(sidebarCollapsedKey, String(collapsed));", self.template)
        self.assertIn("setSidebarState(readStoredSidebarCollapsed(), false);", self.template)
        self.assertIn("setSidebarState(!adminLayout.classList.contains('sidebar-collapsed'), true);", self.template)
        self.assertIn("document.documentElement.classList.remove('admin-sidebar-preload');", self.template)
        self.assertNotIn("localStorage.setItem(sidebarPinnedKey", self.template)
        self.assertNotIn("localStorage.setItem(sidebarExpandedKey", self.template)

    def test_sidebar_does_not_expand_or_collapse_on_hover_or_focus(self):
        self.assertNotIn('function shouldKeepSidebarExpanded()', self.template)
        self.assertNotIn("sidebar.matches(':hover')", self.template)
        self.assertNotIn('function syncAutoSidebarExpansion()', self.template)
        self.assertNotIn('openAutoSidebar();', self.template)
        self.assertNotIn('closeAutoSidebar();', self.template)
        self.assertNotIn("sidebar.addEventListener('mouseenter'", self.template)
        self.assertNotIn("sidebar.addEventListener('mouseleave'", self.template)
        self.assertNotIn("sidebar.addEventListener('focusin'", self.template)
        self.assertNotIn("sidebar.addEventListener('focusout'", self.template)
        self.assertNotIn(':has(.sidebar:hover)', self.template)
        self.assertNotIn(':has(.sidebar:focus-within)', self.template)

    def test_sidebar_link_navigation_does_not_change_collapse_state(self):
        self.assertIn('function neutralizeSidebarToggleAttributes()', self.template)
        self.assertIn("sidebar.querySelectorAll('[data-toggle=\"sidebar\"], [data-bs-toggle=\"sidebar\"]')", self.template)
        self.assertIn("item.removeAttribute('data-toggle');", self.template)
        self.assertIn("neutralizeSidebarToggleAttributes();", self.template)
        self.assertNotIn('persistSidebarState(false, true);', self.template)
        self.assertNotIn('persistSidebarState(false, false);', self.template)
        self.assertNotIn("event.target.closest('a[href]')", self.template)
        self.assertNotIn("sidebar.addEventListener('click'", self.template)
        self.assertNotIn("sessionStorage", self.template)

    def test_sidebar_uses_compact_vertical_spacing(self):
        self.assertIn('.sidebar-nav {\n    padding: 0.5rem 0;', self.admin_css)
        self.assertIn('.sidebar-section {\n    margin-bottom: 0.65rem;', self.admin_css)
        self.assertIn('.sidebar-section:last-child {\n    margin-bottom: 0;', self.admin_css)
        self.assertIn('padding: 0.25rem 1.1rem;', self.admin_css)
        self.assertIn('margin-bottom: 0.15rem;', self.admin_css)
        self.assertIn('min-height: 40px;', self.admin_css)
        self.assertIn('padding: 0.55rem 1.1rem;', self.admin_css)
        self.assertIn('font-size: 0.92rem;', self.admin_css)
        self.assertIn('line-height: 1.2;', self.admin_css)
        self.assertIn('margin-right: 0.625rem;', self.admin_css)
        self.assertIn('padding: 0.55rem 0;', self.template)

    def test_sidebar_header_aligns_with_topbar_in_both_states(self):
        self.assertIn('--topbar-height: 64px;', self.admin_css)
        self.assertIn('height: 100vh;', self.admin_css)
        self.assertIn('.topbar {\n    height: var(--topbar-height);', self.admin_css)
        self.assertIn(
            '.sidebar-header {\n'
            '    width: 279px;\n'
            '    height: 64px;\n'
            '    max-height: 64px;\n'
            '    box-sizing: border-box;\n'
            '    flex: 0 0 64px;\n'
            '    overflow: hidden;',
            self.admin_css,
        )
        self.assertIn('padding: 0 1.25rem;', self.admin_css)
        self.assertIn('.sidebar-branding {\n            display: flex;', self.template)
        self.assertIn('align-items: center;', self.template)
        self.assertIn('height: 100%;', self.template)
        self.assertIn(
            'html[data-admin-sidebar-collapsed="true"] .admin-layout .sidebar-header {\n'
            '                width: 100%;\n'
            '                height: 64px;\n'
            '                max-height: 64px;',
            self.template,
        )
        self.assertIn(
            'html[data-admin-sidebar-collapsed="true"] .admin-layout .sidebar-branding {\n'
            '                align-items: center;\n'
            '                justify-content: center;',
            self.template,
        )
        self.assertIn('padding: 0 0.5rem;', self.template)

    def test_internal_system_screens_use_admin_sidebar_layout(self):
        selecionar_pasta = (self.templates_dir / 'documentos' / 'selecionar_pasta.html').read_text(
            encoding='utf-8'
        )
        download_lote_avancado = (
            self.templates_dir / 'documentos' / 'download_lote_avancado.html'
        ).read_text(encoding='utf-8')

        self.assertIn("{% extends 'layouts/painel.html' %}", selecionar_pasta)
        self.assertNotIn("extends 'layouts/public.html'", selecionar_pasta)
        self.assertIn('download-lote-content fade-in', download_lote_avancado)
        self.assertNotIn('main-content fade-in', download_lote_avancado)
