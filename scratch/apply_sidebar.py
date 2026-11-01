# Script para atualizar templates/base.html com a nova Barra Lateral Recolhivel e Mobile Drawer
import re

caminho = "templates/base.html"
with open(caminho, "r", encoding="utf-8") as f:
    conteudo = f.read()

# 1. Atualizar CSS no <style>
css_sidebar = """
    /* --- SIDEBAR RESPONSIVA & RECOLHÍVEL (DESKTOP) --- */
    @media (min-width: 768px) {
      #app-sidebar {
        width: 16rem;
        transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      }
      #main-wrapper {
        padding-left: 16rem;
        transition: padding-left 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      }
      html.sidebar-collapsed #app-sidebar {
        width: 5rem;
      }
      html.sidebar-collapsed #main-wrapper {
        padding-left: 5rem;
      }
      html.sidebar-collapsed .sidebar-text {
        display: none !important;
      }
      html.sidebar-collapsed .sidebar-expanded-only {
        display: none !important;
      }
      html.sidebar-collapsed .sidebar-collapsed-only {
        display: flex !important;
      }
      html:not(.sidebar-collapsed) .sidebar-collapsed-only {
        display: none !important;
      }
      /* Tooltip flutuante ativo apenas no modo recolhido */
      html.sidebar-collapsed .sidebar-item:hover .sidebar-tooltip,
      html.sidebar-collapsed .sidebar-item:focus-within .sidebar-tooltip {
        opacity: 1;
        visibility: visible;
        transform: translateX(0);
      }
    }
    .sidebar-tooltip {
      opacity: 0;
      visibility: hidden;
      transform: translateX(-6px);
      transition: opacity 0.15s ease, transform 0.15s ease, visibility 0.15s;
    }
    @media (max-width: 767px) {
      #app-sidebar {
        display: none;
      }
      #main-wrapper {
        padding-left: 0 !important;
      }
    }
"""

# Inserir o CSS antes de </style>
if "/* --- SIDEBAR RESPONSIVA & RECOLHÍVEL (DESKTOP) --- */" not in conteudo:
    conteudo = conteudo.replace("</style>", css_sidebar + "\n  </style>")

print("CSS atualizado com sucesso.")

