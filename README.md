# Detector de Unfollowers de Instagram

**Librerías:** Se utilizó `Selenium`. Decidí implementar la automatización web porque es la única forma robusta de extraer estos datos actualmente sin usar su API oficial (que está bloqueada para este tipo de extracción). Esta librería automatiza un navegador real y maneja el scroll automáticamente, simulando el comportamiento humano para evitar que marquen la cuenta de IG por actividad inusual.

Esta librería automatiza un navegador real. El scroll de las listas se hace manipulando directamente el contenedor interno vía JavaScript, evitando eventos de mouse que rompen la interfaz de Instagram, y con pausas entre cada carga para no saturar de pedidos al servidor.

---

## 🛠️ Requisitos Previos

1. **Python:** Python 3.8 o superior instalado para ejecutar el script.
2. **PIP:** Gestor de paquetes de Python.
3. **Google Chrome:** Navegador instalado en tu equipo (Selenium lo abrirá automáticamente).

## 📦 Instalación

Abre tu terminal (o consola) e instala las dependencias necesarias ejecutando:

```bash
pip install selenium pandas openpyxl
