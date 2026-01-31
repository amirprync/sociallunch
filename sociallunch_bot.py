"""
Social Lunch - Agente de Pedido Automático (Versión Cloud)
==========================================================
Automatiza el pedido mensual de comida en Social Lunch.

Variables de entorno requeridas:
    SOCIALLUNCH_USER: Email de login
    SOCIALLUNCH_PASS: Contraseña

Uso:
    python sociallunch_bot.py
    python sociallunch_bot.py --visible    # Ver navegador
    python sociallunch_bot.py --dry-run    # Simular sin pedir
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
        
        # Preferencias de comida (en minúsculas para comparación)
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
        
        # Timeouts
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
    time.sleep(2)
    
    # Completar login
    page.fill('input[type="text"]', config["usuario"])
    page.fill('input[type="password"]', config["password"])
    
    # Submit
    page.click('input[type="submit"]')
    
    page.wait_for_load_state("networkidle")
    time.sleep(5)  # Espera más larga para que cargue todo
    
    # Verificar login
    if page.locator("text=HOLA").count() > 0:
        print("✅ Login exitoso")
        return True
    else:
        print("❌ Error en login")
        return False


def obtener_dias_disponibles(page):
    """
    Obtiene días disponibles para pedir.
    
    Estructura del HTML:
    - div con id="date_2026-02-XX" 
    - class contiene "date" y "futuro"
    - NO contiene "sin-servicio" ni "con-pedido"
    """
    print("\n📅 Buscando días disponibles...")
    
    # Esperar explícitamente a que el calendario cargue
    print("   Esperando que cargue el calendario...")
    try:
        page.wait_for_selector('div[id^="date_"]', timeout=15000)
        print("   ✅ Calendario detectado")
    except:
        print("   ❌ No se detectó el calendario")
        return []
    
    # Espera adicional para que terminen de cargar todos los días
    time.sleep(3)
    
    # Buscar todos los divs que tienen ID que empieza con "date_"
    todos_los_dias = page.locator('div[id^="date_"]').all()
    
    print(f"   Total de días en calendario: {len(todos_los_dias)}")
    
    dias_disponibles = []
    for elem in todos_los_dias:
        try:
            clase = elem.get_attribute("class") or ""
            dia_id = elem.get_attribute("id") or ""
            
            # Debug: mostrar qué encontró
            print(f"   DEBUG: {dia_id} -> clase: '{clase}'")
            
            # Verificar condiciones:
            # 1. Tiene "futuro" en la clase
            # 2. NO tiene "sin-servicio"
            # 3. NO tiene "con-pedido"
            # 4. NO tiene "pasado"
            es_futuro = "futuro" in clase
            sin_servicio = "sin-servicio" in clase
            con_pedido = "con-pedido" in clase
            es_pasado = "pasado" in clase
            
            if es_futuro and not sin_servicio and not con_pedido and not es_pasado:
                # Obtener el número del día
                numero_elem = elem.locator(".dia_numero")
                if numero_elem.count() > 0:
                    numero = numero_elem.inner_text().strip()
                    
                    dias_disponibles.append({
                        "elemento": elem,
                        "id": dia_id,
                        "numero": numero
                    })
                    print(f"   ✅ Día {numero} disponible para pedir")
        except Exception as e:
            print(f"   Error procesando día: {e}")
            continue
    
    print(f"\n   📊 Resumen: {len(dias_disponibles)} días para pedir")
    return dias_disponibles


def seleccionar_ubicacion(page, config):
    """Selecciona COHEN PISO 1 en el modal."""
    print("   📍 Seleccionando ubicación...")
    
    try:
        # Esperar a que aparezca el modal
        page.wait_for_selector(f'text="{config["ubicacion"]}"', timeout=5000)
        page.click(f'text="{config["ubicacion"]}"')
        time.sleep(config["delay_entre_acciones"] / 1000)
        print("   ✅ Ubicación seleccionada")
        return True
    except PlaywrightTimeout:
        # Puede que no aparezca el modal si ya está seleccionada
        print("   ⏭️ Modal de ubicación no apareció, continuando...")
        return True
    except Exception as e:
        print(f"   ⚠️ Error en ubicación: {e}")
        return True


def seleccionar_item_de_categoria(page, config, categoria, keywords, descripcion):
    """
    Va a una categoría y selecciona un item que coincida con los keywords.
    La selección se hace mediante checkboxes dentro de labels.
    """
    print(f"   🍽️ Seleccionando {descripcion}...")
    
    try:
        # Click en la categoría usando el atributo data-dimension
        page.click(f'div[data-dimension="{categoria}"]', timeout=5000)
        time.sleep(config["delay_entre_acciones"] / 1000)
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        
        # Los items son inputs con clase "selection_items" y tienen data-desc con la descripción
        items = page.locator('input.selection_items').all()
        
        if not items:
            print(f"   ⚠️ No hay items en {categoria}")
            return False
        
        print(f"   📋 Encontrados {len(items)} items en {categoria}")
        
        # Buscar items que coincidan con los keywords
        items_coincidentes = []
        
        for item in items:
            try:
                # Obtener la descripción del item
                desc = item.get_attribute("data-desc") or ""
                desc_lower = desc.lower()
                
                # Verificar si coincide con algún keyword
                for keyword in keywords:
                    if keyword.lower() in desc_lower:
                        items_coincidentes.append({"elemento": item, "desc": desc})
                        break
            except:
                continue
        
        # Si encontró coincidencias, elegir una al azar
        if items_coincidentes:
            elegido = random.choice(items_coincidentes)
            print(f"   ✓ Seleccionando: {elegido['desc'][:50]}...")
            elegido["elemento"].click()
            time.sleep(config["delay_entre_acciones"] / 1000)
            print(f"   ✅ {descripcion.capitalize()} agregado/a")
            return True
        else:
            # Si no hay coincidencias, tomar el primero disponible
            print(f"   ⚠️ No se encontró preferencia, tomando primera opción")
            primer_item = items[0]
            desc = primer_item.get_attribute("data-desc") or "item"
            print(f"   ✓ Seleccionando: {desc[:50]}...")
            primer_item.click()
            time.sleep(config["delay_entre_acciones"] / 1000)
            print(f"   ✅ {descripcion.capitalize()} agregado/a (opción alternativa)")
            return True
            
    except PlaywrightTimeout:
        print(f"   ⚠️ Categoría {categoria} no encontrada")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def confirmar_pedido(page):
    """Confirma el pedido clickeando CONFIRMAR."""
    print("   💾 Confirmando pedido...")
    
    try:
        # Intentar varios selectores
        page.click('text=/confirmar/i', timeout=5000)
        time.sleep(2)
        print("   ✅ Pedido confirmado")
        return True
    except Exception as e:
        print(f"   ⚠️ Error al confirmar: {e}")
        return False


def volver_al_calendario(page, config):
    """Vuelve a la pantalla del calendario."""
    try:
        # Intentar botón VOLVER
        page.click('text="VOLVER"', timeout=3000)
    except:
        try:
            # Alternativa: ir directo a la URL
            page.goto(config["url"])
        except:
            pass
    
    time.sleep(2)
    page.wait_for_load_state("networkidle")


def procesar_dia(page, config, dia_info, dry_run=False):
    """Procesa el pedido para un día específico."""
    numero = dia_info["numero"]
    dia_id = dia_info["id"]
    
    print(f"\n{'='*50}")
    print(f"📆 Procesando día {numero} ({dia_id})")
    print(f"{'='*50}")
    
    if dry_run:
        print("   [DRY RUN] Simulando...")
        return True
    
    try:
        # Click en el día
        dia_info["elemento"].click()
        time.sleep(config["delay_entre_acciones"] / 1000)
        
        # Seleccionar ubicación si aparece el modal
        seleccionar_ubicacion(page, config)
        
        # Esperar a que cargue el menú
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # Verificar si hay servicio
        if page.locator('text="DÍA SIN SERVICIO"').count() > 0:
            print("   ⏭️ Día sin servicio, saltando...")
            volver_al_calendario(page, config)
            return True
        
        # Seleccionar ensalada
        seleccionar_item_de_categoria(
            page, config,
            "ENSALADAS",
            config["ensaladas_keywords"],
            "ensalada"
        )
        
        # Seleccionar postre
        seleccionar_item_de_categoria(
            page, config,
            "POSTRES",
            config["postres_preferidos"],
            "postre"
        )
        
        # Seleccionar bebida
        seleccionar_item_de_categoria(
            page, config,
            "BEBIDAS",
            config["bebidas_preferidas"],
            "bebida"
        )
        
        # Confirmar pedido
        confirmar_pedido(page)
        
        # Volver al calendario para el siguiente día
        volver_al_calendario(page, config)
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error procesando día {numero}: {e}")
        # Intentar volver al calendario
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
    print(f"👤 Usuario: ***")
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
            
            # Obtener días disponibles
            dias = obtener_dias_disponibles(page)
            
            if not dias:
                print("\n✅ No hay días pendientes de pedir (ya están todos con pedido o sin servicio)")
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
            print(f"✅ Pedidos exitosos: {exitos}")
            print(f"❌ Pedidos fallidos: {errores}")
            print(f"📅 Total días procesados: {len(dias)}")
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
