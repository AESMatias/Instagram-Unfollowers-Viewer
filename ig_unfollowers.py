from selenium import webdriver
from selenium.webdriver.common.by import By
import pandas as pd
import time
import sys
import os

def main():

    options = webdriver.ChromeOptions()
    options.add_argument("--disable-notifications")
    driver = webdriver.Chrome(options=options)

    try:
        driver.get("https://www.instagram.com/accounts/login/")

        print("\n" + "="*50)
        print("*** PASO 1: LOGIN MANUAL ***")
        print("1. Inicia sesión manualmente en Chrome.")
        print("2. Ve a tu perfil.")
        print("="*50)

        input("\n> Presiona ENTER aquí en la terminal cuando ya estés viendo tu perfil en Chrome... ")

        def extraer_y_bajar(tipo_lista):
            # Todo (lectura de usuarios + scroll) se hace en un solo execute_script
            # para no tener que mover el mouse ni el teclado entre pasos.
            js_leer_y_scrollear = """
            let dialog = document.querySelector('div[role="dialog"]');
            if (!dialog) return { error: "No se encontró la ventana" };

            let links = dialog.querySelectorAll('a');
            let users = {};
            let hit_suggestions = false;
            let descartados = [];  // debug: quién se descarta y por qué

            // --- Ubicamos el ENCABEZADO real de la sección de sugerencias (aparece
            // UNA sola vez en el documento). Las filas de sugerencias no llevan
            // ninguna marca de texto propia, así que la única señal confiable es
            // su posición en el DOM respecto a este encabezado.
            // OJO: React suele meter texto oculto para lectores de pantalla al
            // principio del modal -> por eso exigimos que sea VISIBLE de verdad. ---
            function esVisible(el) {
                if (!el) return false;
                let rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return false;
                let style = window.getComputedStyle(el);
                if (style.visibility === 'hidden' || style.display === 'none') return false;
                if (el.closest('[aria-hidden="true"]')) return false;
                // Descartamos clases típicas de texto solo-para-lectores-de-pantalla
                if (/sr-only|visually-hidden|screen-reader/i.test(el.className || '')) return false;
                return true;
            }

            let heading = null;
            let headingTextoEncontrado = "";
            let headingKeywordsExactas = ['suggested for you', 'sugerencias para ti', 'sugerido para ti', 'discover people', 'descubre personas'];
            let posiblesHeadings = dialog.querySelectorAll('div, span, h1, h2, h3, h4, header, p');
            for (let el of posiblesHeadings) {
                let ownText = Array.from(el.childNodes)
                    .filter(n => n.nodeType === Node.TEXT_NODE)
                    .map(n => n.textContent.trim())
                    .join(' ')
                    .toLowerCase();
                if (ownText.length === 0 || ownText.length > 40) continue;
                if (!headingKeywordsExactas.some(k => ownText.includes(k))) continue;
                if (!esVisible(el)) continue;  // ignoramos el texto fantasma de accesibilidad
                heading = el;
                headingTextoEncontrado = ownText;
                break;
            }

            links.forEach(a => {
                let href = a.getAttribute('href');
                if (!href) return;

                let parts = href.split('?')[0].split('/').filter(Boolean);
                let username = parts[parts.length - 1];

                if (!username || ['explore', 'reels', 'p', 'locations'].includes(username)) return;
                if (a.innerText.trim() !== username) return;

                let row = a;
                let foundBtn = false;
                while (row && row !== dialog) {
                    if (row.querySelector('button')) {
                        foundBtn = true;
                        break;
                    }
                    row = row.parentElement;
                }
                if (!foundBtn) {
                    descartados.push({user: username, motivo: "sin_boton"});
                    return;
                }

                // Corte estructural: si esta fila aparece DESPUÉS del encabezado de
                // sugerencias en el documento, es sugerencia -> paramos ahí, siempre.
                if (heading) {
                    let rel = heading.compareDocumentPosition(a);
                    if (rel & Node.DOCUMENT_POSITION_FOLLOWING) {
                        hit_suggestions = true;
                        descartados.push({user: username, motivo: "despues_del_encabezado_sugerencias"});
                        return;
                    }
                }

                let lines = row.innerText.split('\\n').map(l => l.trim()).filter(Boolean);
                let btnWords = ['seguir', 'follow', 'siguiendo', 'following', 'eliminar', 'remove', 'solicitado', 'requested', 'confirmar'];
                let textLines = lines.filter(l => !btnWords.includes(l.toLowerCase()));

                if (username in users) {
                    return; // ya lo teníamos, no es un descarte real
                }
                users[username] = (textLines.length > 1) ? textLines[1] : "";
            });

            // SCROLL 100% VIA JS, SIN MOUSE NI TECLADO
            // Buscamos el div interno con scroll real (scrollHeight > clientHeight)
            let scrollable = null;
            let candidatos = dialog.querySelectorAll('div');
            for (let el of candidatos) {
                if (el.scrollHeight > el.clientHeight + 10 && el.clientHeight > 150) {
                    scrollable = el;
                    break;
                }
            }

            let scroll_hizo_algo = false;
            let scrollHeightAntes = scrollable ? scrollable.scrollHeight : 0;
            if (scrollable) {
                window.__ig_scrollable = scrollable;  // guardamos referencia para sondeo rápido
                let antes = scrollable.scrollTop;
                // Salto grande de nuevo (rápido) - el sondeo activo se encarga de esperar
                // lo justo y necesario, así que ya no hace falta ser conservador acá.
                scrollable.scrollTop = scrollable.scrollTop + Math.floor(scrollable.clientHeight * 0.85);
                scrollable.dispatchEvent(new Event('scroll', { bubbles: true }));
                scroll_hizo_algo = (scrollable.scrollTop !== antes);
            }

            return { users: users, stop: hit_suggestions, scrolled: scroll_hizo_algo, found_scrollable: !!scrollable, scrollHeight: scrollHeightAntes, descartados: descartados, heading_texto: headingTextoEncontrado };
            """

            data_total = {}
            intentos_sin_avance = 0
            MAX_INTENTOS_SIN_AVANCE = 8  # con 8 intentos sin cambios ya alcanza para confirmar que se llegó al final
            ultimo_scrollHeight = -1

            # Script chico para chequear rápido si ya cargó algo nuevo, sin tener que
            # correr de nuevo todo el parseo pesado de usuarios.
            js_sondeo_rapido = "return window.__ig_scrollable ? window.__ig_scrollable.scrollHeight : -1;"

            def esperar_avance(scrollHeight_previo, timeout=4.0, intervalo=0.2):
                # Va chequeando cada 0.2s si el alto de la lista creció. Si Instagram
                # responde rápido, seguimos altiro; si no, esperamos hasta el timeout.
                inicio = time.time()
                while time.time() - inicio < timeout:
                    time.sleep(intervalo)
                    actual = driver.execute_script(js_sondeo_rapido)
                    if actual != scrollHeight_previo and actual != -1:
                        return True
                return False

            print(f"Iniciando escaneo continuo de {tipo_lista}...")

            while True:
                resultado = driver.execute_script(js_leer_y_scrollear)

                if resultado.get("error"):
                    print(f"\nError crítico: Abre la lista de {tipo_lista} en Chrome primero.")
                    return {}

                if not resultado.get("found_scrollable"):
                    print("\nAviso: no se encontró el contenedor con scroll interno. Revisa el selector.")

                nuevos_usuarios = resultado.get("users", {})
                flag_parada = resultado.get("stop", False)
                scrollHeight_actual = resultado.get("scrollHeight", 0)

                conteo_anterior = len(data_total)
                data_total.update(nuevos_usuarios)
                conteo_actual = len(data_total)

                sys.stdout.write(f"\r-> {conteo_actual} procesados... (intentos sin avance: {intentos_sin_avance})")
                sys.stdout.flush()

                if flag_parada:
                    heading_txt = resultado.get("heading_texto", "")
                    print(f"\n-> Fin de lista detectado (Sugerencias, encabezado visible: '{heading_txt}'). Total: {conteo_actual}")
                    break

                hubo_usuarios_nuevos = (conteo_actual != conteo_anterior)

                if hubo_usuarios_nuevos:
                    intentos_sin_avance = 0
                    continue  # ya sabemos que hay contenido nuevo, no hace falta sondear

                # No hubo usuarios nuevos en este parseo: sondeamos rápido si el contenedor
                # está creciendo (Instagram todavía está cargando el siguiente lote).
                crecio = esperar_avance(scrollHeight_actual)
                ultimo_scrollHeight = scrollHeight_actual

                if crecio:
                    intentos_sin_avance = 0
                else:
                    intentos_sin_avance += 1
                    if intentos_sin_avance >= MAX_INTENTOS_SIN_AVANCE:
                        print(f"\n-> Fin de lista detectado (Fondo físico). Total: {conteo_actual}")
                        break

            return data_total

        print("\n" + "="*50)
        print("*** PASO 2 - EXTRAER SEGUIDORES ***")
        print("Haz clic en tu lista de 'Seguidores' (Followers) en Chrome para que se abra.")
        print("="*50)
        input("\n>>> Presiona ENTER aquí SOLAMENTE cuando la lista de SEGUIDORES esté abierta... ")

        followers = extraer_y_bajar("Seguidores")

        print("\n" + "="*50)
        print("*** PASO 3 - EXTRAER SEGUIDOS ***")
        print("1. CIERRA la lista de Seguidores en Chrome (usando la X).")
        print("2. Abre tu lista de 'Seguidos' (Following).")
        print("="*50)

        input("\n>>> Presiona ENTER aquí SOLAMENTE cuando la lista de SEGUIDOS esté abierta... ")

        followees = extraer_y_bajar("Seguidos")

        print(f"\n--- LISTA COMPLETA CAPTURADA EN SEGUIDOS ({len(followees)}) ---")
        for u in sorted(followees.keys()):
            print(f"   {u}")

        print("\n*** Cruzando las listas para encontrar unfollowers... ***")
        unfollowers_data = []

        for username, full_name in followees.items():
            if username not in followers:
                unfollowers_data.append({
                    "username": username,
                    "full_name": full_name
                })

        print(f"\nTotal de unfollowers detectados: {len(unfollowers_data)}")

        if unfollowers_data:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            csv_path = os.path.join(current_dir, "no_me_siguen.csv")
            excel_path = os.path.join(current_dir, "no_me_siguen.xlsx")

            df = pd.DataFrame(unfollowers_data)
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            df.to_excel(excel_path, index=False, engine='openpyxl')
            print(f"¡Listo! Archivos generados en:\n- {csv_path}\n- {excel_path}")
        else:
            print("¡Todas las personas que sigues te siguen de vuelta!")

    except Exception as e:
        print(f"\nOcurrió un error crítico general: {e}")
    finally:
        print("\nCerrando navegador...")
        driver.quit()

if __name__ == "__main__":
    main()
