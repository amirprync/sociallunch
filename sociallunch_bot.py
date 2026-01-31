"""
Social Lunch - Agente de Pedido Automático (Versión Cloud)
==========================================================
Este script automatiza el pedido mensual de comida en Social Lunch.

Preferencias configuradas:
- Plato: Cualquier ensalada disponible
- Postre: Alfajor de Chocolate x 60 gr / Cookie / Cuadrado de Limón
- Bebida: Coca Zero / Pepsi Light
- Ubicación: COHEN PISO 1

Variables de entorno requeridas:
    SOCIALLUNCH_USER: Email de login
    SOCIALLUNCH_PASS: Contraseña

Uso local:
    export SOCIALLUNCH_USER="tu@email.com"
    export SOCIALLUNCH_PASS="tupassword"
    python sociallunch_bot.py
    
    # Modo visible (para debug):
    python sociallunch_bot.py --visible
"""

import argparse
import os
import random
import sys
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


# =============================================================================
# CONFIGURACIÓN
# =============================================================================

def get_config():
    """Obtiene configuración desde variables de entorno."""
    usuario = os.environ.get("SOCIALLUNCH_USER")
    password = os.environ.get("SOCIALLUNCH_PASS")
    
    if not usuario or not password:
        print("❌ Error: Variables de entorno no configuradas")
        print("   Configurar SOCIALLUNCH_USER y SOCIALLUNCH_PASS")
        sys.exit(1)
    
    return {
        "url": "https://app.sociallunch.com.ar/",
        "usuario": usuario,
        "password": password,
        "ubicacion": "COHEN PISO 1",
        
        # Preferencias de comida
        "ensaladas_keywords": ["ensalada"],
        
        "postres_preferidos": [
            "alfajor de chocolate",
            "cookie",
            "cuadrado de limon",
            "cuadrado de limón"
        ],
        
        "bebidas_preferidas": [
            "coca zero",
            "coca-cola zero",
            "pepsi light",
            "pepsi zero"
        ],
        
        # Timeouts (en milisegundos)
        "timeout_navegacion": 30000,
        "timeout_elemento": 10000,
        "delay_entre_acciones": 1500,
    }


# =============================================================================
# FUNCIONES PRINCIPALES
# =============================================================================

def login(page, config):
    """Realiza el login en Social Lunch."""
    print("🔐 Iniciando sesión...")
    
    page.goto(config["url"], timeout=config["timeout_navegacion"])
    page.wait_for_load_state("networkidle")
    
    # Completar formulario de login
    # Intentar varios selectores posibles para el campo de email
    email_selectors = [
        'input[type="email"]',
        'input[type="text"]',
        'input[name="mail"]',
        'input[name="email"]',
        'input[name="user"]',
        'input[placeholder*="mail" i]',
        'input[placeholder*="usuario" i]'
    ]
    
    for selector in email_selectors:
        try:
            if page.locator(selector).count() > 0:
                page.fill(selector, config["usuario"])
                break
        except:
            continue
    
    # Campo de contraseña
    page.fill('input[type="password"]', config["password"])
    
    # Click en botón de login
    login_selectors = [
        'input[type="submit"]',
        'button[type="submit"]',
        'button:has-text("Ingresar")',
        'button:has-text("Entrar")',
        'button:has-text("Login")',
        '.btn-login'
    ]
    
    for selector in login_selectors:
        try:
            if page.locator(selector).count() > 0:
                page.click(selector)
                break
        except:
            continue
    
    # Esperar a que cargue el dashboard
    page.wait_for_load_state("networkidle")
    time.sleep(3)
    
    # Verificar login exitoso
    if page.locator("text=HOLA").count() > 0:
        print("✅ Login exitoso")
        return True
    else:
        print("❌ Error en login - verificar credenciales")
        return False


def obtener_dias_disponibles(page):
    """Obtiene la lista de días con servicio disponible."""
    print("\n📅 Buscando días disponibles...")
    
    # Esperar a que cargue el calendario
    time.sleep(2)
    
    # Buscar elementos del calendario - los días son divs con números
    # Los disponibles están en verde (sin clase disabled/inactive)
    dias_disponibles = []
    
    # Intentar encontrar los días del calendario
    # La estructura típica es un contenedor con días clickeables
    posibles_selectores = [
        '.calendar-day:not(.disabled)',
        '[class*="day"]:not([class*="disabled"])',
        '[class*="fecha"]:not([class*="disabled"])',
        'div[class*="active"]'
    ]
    
    for selector in posibles_selectores:
        try:
            elementos = page.locator(selector).all()
            if elementos:
                for elem in elementos:
                    try:
                        texto = elem.inner_text().strip()
                        # Verificar que sea un número de día válido
                        if texto.isdigit() and 1 <= int(texto) <= 31:
                            # Verificar que esté visible y sea clickeable
                            if elem.is_visible():
                                # Verificar el color de fondo o estilo
                                style = elem.evaluate("el => window.getComputedStyle(el).backgroundColor")
                                # Los días activos suelen tener fondo verde o similar
                                dias_disponibles.append({
                                    "elemento": elem,
                                    "numero": int(texto),
                                    "style": style
                                })
                    except:
                        continue
                break
        except:
            continue
    
    # Filtrar duplicados por número de día
    dias_unicos = {}
    for dia in dias_disponibles:
        num = dia["numero"]
        if num not in dias_unicos:
            dias_unicos[num] = dia
    
    dias_finales = sorted(dias_unicos.values(), key=lambda x: x["numero"])
    
    print(f"   Encontrados {len(dias_finales)} días potencialmente disponibles")
    return dias_finales


def seleccionar_ubicacion(page, config):
    """Selecciona la ubicación en el modal."""
    print("   📍 Seleccionando ubicación...")
    
    ubicacion = config["ubicacion"]
    
    try:
        # Esperar modal
        time.sleep(1)
        
        # Buscar el botón con la ubicación
        selectores = [
            f'button:has-text("{ubicacion}")',
            f'div:has-text("{ubicacion}")',
            f'text="{ubicacion}"',
            f'*:has-text("{ubicacion}")'
        ]
        
        for selector in selectores:
            try:
                elem = page.locator(selector).first
                if elem.is_visible():
                    elem.click()
                    time.sleep(config["delay_entre_acciones"] / 1000)
                    return True
            except:
                continue
        
        print("   ⚠️ No se encontró selector de ubicación, continuando...")
        return True  # Puede que no siempre aparezca
        
    except Exception as e:
        print(f"   ⚠️ Error en ubicación: {e}")
        return True


def seleccionar_item_de_categoria(page, config, categoria, keywords, descripcion):
    """Navega a una categoría y selecciona un item."""
    print(f"   🍽️ Buscando {descripcion}...")
    
    try:
        # Click en la categoría del menú
        page.click(f'text="{categoria}"', timeout=5000)
        time.sleep(config["delay_entre_acciones"] / 1000)
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        
        # Buscar items en la página
        # Los items típicamente tienen una card con nombre y botón AGREGAR
        items_encontrados = []
        
        # Buscar todos los textos visibles que coincidan con keywords
        for keyword in keywords:
            try:
                elementos = page.locator(f'text=/{keyword}/i').all()
                for elem in elementos:
                    try:
                        if elem.is_visible():
                            items_encontrados.append(elem)
                    except:
                        continue
            except:
                continue
        
        if items_encontrados:
            # Tomar uno al azar
            item = random.choice(items_encontrados)
            
            # Buscar el botón AGREGAR cercano
            # Subir al contenedor padre y buscar el botón
            try:
                # Intentar encontrar AGREGAR en el mismo contenedor
                parent = item.locator('xpath=ancestor::*[contains(@class,"card") or contains(@class,"item") or contains(@class,"producto")][1]')
                if parent.count() > 0:
                    boton = parent.locator('text="AGREGAR"')
                    if boton.count() > 0:
                        boton.first.click()
                        print(f"   ✅ {descripcion.capitalize()} agregado/a")
                        time.sleep(config["delay_entre_acciones"] / 1000)
                        return True
            except:
                pass
            
            # Alternativa: buscar cualquier botón AGREGAR visible
            try:
                page.click('text="AGREGAR"', timeout=3000)
                print(f"   ✅ {descripcion.capitalize()} agregado/a")
                time.sleep(config["delay_entre_acciones"] / 1000)
                return True
            except:
                pass
        
        # Si no encontró con keywords, tomar el primero disponible
        try:
            page.click('text="AGREGAR"', timeout=3000)
            print(f"   ✅ {descripcion.capitalize()} agregado/a (opción disponible)")
            time.sleep(config["delay_entre_acciones"] / 1000)
            return True
        except:
            print(f"   ⚠️ No se encontró {descripcion}")
            return False
            
    except PlaywrightTimeout:
        print(f"   ⚠️ Categoría {categoria} no disponible")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def confirmar_pedido(page, config):
    """Confirma el pedido del día."""
    print("   💾 Confirmando pedido...")
    
    try:
        page.click('text="CONFIRMAR"', timeout=5000)
        time.sleep(2)
        print("   ✅ Pedido confirmado")
        return True
    except:
        # Intentar con otros selectores
        try:
            page.click('button:has-text("CONFIRMAR")', timeout=3000)
            time.sleep(2)
            print("   ✅ Pedido confirmado")
            return True
        except:
            print("   ⚠️ No se pudo confirmar")
            return False


def procesar_dia(page, config, dia_info, dry_run=False):
    """Procesa el pedido para un día específico."""
    numero_dia = dia_info["numero"]
    print(f"\n{'='*50}")
    print(f"📆 Procesando día {numero_dia}")
    print(f"{'='*50}")
    
    if dry_run:
        print("   [DRY RUN] Simulando...")
        return True
    
    try:
        # Click en el día
        dia_info["elemento"].click()
        time.sleep(config["delay_entre_acciones"] / 1000)
        
        # Seleccionar ubicación
        seleccionar_ubicacion(page, config)
        
        # Esperar carga del menú
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # Verificar si el día tiene servicio
        if page.locator('text="DÍA SIN SERVICIO"').count() > 0:
            print("   ⏭️ Día sin servicio, saltando...")
            try:
                page.click('text="VOLVER"', timeout=3000)
            except:
                page.go_back()
            return True
        
        # Seleccionar comida
        seleccionar_item_de_categoria(page, config, "ENSALADAS", config["ensaladas_keywords"], "ensalada")
        seleccionar_item_de_categoria(page, config, "POSTRES", config["postres_preferidos"], "postre")
        seleccionar_item_de_categoria(page, config, "BEBIDAS", config["bebidas_preferidas"], "bebida")
        
        # Confirmar
        confirmar_pedido(page, config)
        
        # Volver al calendario
        time.sleep(1)
        try:
            page.click('text="VOLVER"', timeout=3000)
        except:
            try:
                page.go_back()
            except:
                page.goto(config["url"])
        
        time.sleep(2)
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        # Intentar volver al inicio
        try:
            page.goto(config["url"])
            time.sleep(2)
        except:
            pass
        return False


def ejecutar_agente(visible=False, dry_run=False):
    """Función principal del agente."""
    config = get_config()
    
    print("\n" + "="*60)
    print("🤖 SOCIAL LUNCH - AGENTE DE PEDIDO AUTOMÁTICO")
    print("="*60)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"👤 Usuario: {config['usuario']}")
    print(f"📍 Ubicación: {config['ubicacion']}")
    if dry_run:
        print("⚠️  MODO DRY-RUN: No se harán pedidos reales")
    print("="*60)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not visible,
            slow_mo=500 if visible else 0
        )
        
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        page = context.new_page()
        page.set_default_timeout(config["timeout_elemento"])
        
        try:
            # Login
            if not login(page, config):
                print("\n❌ Login fallido. Abortando.")
                sys.exit(1)
            
            # Obtener días
            dias = obtener_dias_disponibles(page)
            
            if not dias:
                print("\n⚠️ No se encontraron días disponibles")
                sys.exit(0)
            
            print(f"\n📋 Días a procesar: {[d['numero'] for d in dias]}")
            
            # Procesar cada día
            exitos = 0
            errores = 0
            
            for dia in dias:
                if procesar_dia(page, config, dia, dry_run):
                    exitos += 1
                else:
                    errores += 1
                time.sleep(1)
            
            # Resumen
            print("\n" + "="*60)
            print("📊 RESUMEN")
            print("="*60)
            print(f"✅ Exitosos: {exitos}")
            print(f"❌ Fallidos: {errores}")
            print("="*60)
            
            if errores > 0:
                sys.exit(1)
                
        except Exception as e:
            print(f"\n❌ Error general: {e}")
            sys.exit(1)
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Social Lunch Bot")
    parser.add_argument("--visible", action="store_true", help="Mostrar navegador")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin ejecutar")
    
    args = parser.parse_args()
    ejecutar_agente(visible=args.visible, dry_run=args.dry_run)
