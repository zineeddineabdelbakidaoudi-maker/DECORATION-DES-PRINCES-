"""
PeintPro Mobile Web API Service.
Runs embedded Uvicorn server in a background thread for iPhone & Mobile PWA connectivity.
"""
import os
import sys
import socket
import threading
import logging
import psycopg2
import psycopg2.extras
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn


def fmt_price(value):
    try:
        return f"{float(value):,.2f}".replace(",", " ") + " DA"
    except:
        return f"{value} DA"


logger = logging.getLogger("PeintPro.MobileAPI")


def get_connection():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url: raise Exception("DATABASE_URL missing")
    conn = psycopg2.connect(db_url)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn

def exec_query(c, query, params=()):
    pg_query = query.replace("?", "%s")
    pg_query = pg_query.replace("substr(sale_date", "substr(CAST(sale_date AS text)")
    pg_query = pg_query.replace("substr(s.sale_date", "substr(CAST(s.sale_date AS text)")
    pg_query = pg_query.replace("substr(payment_date", "substr(CAST(payment_date AS text)")
    pg_query = pg_query.replace("substr(date", "substr(CAST(date AS text)")
    pg_query = pg_query.replace("substr(expense_date", "substr(CAST(expense_date AS text)")
    pg_query = pg_query.replace("substr(return_date", "substr(CAST(return_date AS text)")
    pg_query = pg_query.replace("IFNULL(", "COALESCE(")
    c.execute(pg_query, params)
    return c

api_app = FastAPI(title="PeintPro Mobile API", version="1.0")


def init_db():
    schema = """
CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY, name TEXT, created_at TEXT, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT, category_id INTEGER, barcode TEXT, unit_type TEXT, sell_price NUMERIC, price_per_kg NUMERIC, buy_price NUMERIC, buy_price_per_kg NUMERIC, stock_qty NUMERIC, bidon_capacity NUMERIC, closed_bidons INTEGER, open_bidon_kg NUMERIC, allows_preparation INTEGER, preparation_cost_per_kg NUMERIC, active INTEGER, created_at TEXT, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, name TEXT, phone TEXT, address TEXT, created_at TEXT, avoir NUMERIC, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY, client_id INTEGER, location_name TEXT, status TEXT, created_at TEXT, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS transactions_log (id INTEGER PRIMARY KEY, date TEXT, type TEXT, description TEXT, amount NUMERIC, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY, sale_date TEXT, total NUMERIC, preparation_type TEXT, preparation_total NUMERIC, remise NUMERIC, grand_total NUMERIC, payment_method TEXT, client_id INTEGER, project_id INTEGER, client_name TEXT, is_debt INTEGER, notes TEXT, versement_total NUMERIC, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS sale_items (id INTEGER PRIMARY KEY, sale_id INTEGER, product_id INTEGER, product_name TEXT, unit_type TEXT, quantity NUMERIC, unit_price NUMERIC, unit_cost_price NUMERIC, subtotal NUMERIC, has_preparation INTEGER, preparation_cost NUMERIC, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY, supplier TEXT, purchase_date TEXT, total NUMERIC, notes TEXT, supplier_id INTEGER, paid_amount NUMERIC, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS purchase_items (id INTEGER PRIMARY KEY, purchase_id INTEGER, product_id INTEGER, product_name TEXT, quantity NUMERIC, unit_price NUMERIC, subtotal NUMERIC, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS debts (id INTEGER PRIMARY KEY, client_id INTEGER, project_id INTEGER, client_name TEXT, phone TEXT, sale_id INTEGER, amount NUMERIC, paid NUMERIC, remaining NUMERIC, status TEXT, created_at TEXT, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS debt_payments (id INTEGER PRIMARY KEY, debt_id INTEGER, amount NUMERIC, payment_date TEXT, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS suppliers (id INTEGER PRIMARY KEY, name TEXT, phone TEXT, address TEXT, initial_debt NUMERIC, created_at TEXT, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS supplier_payments (id INTEGER PRIMARY KEY, supplier_id INTEGER, amount NUMERIC, payment_date TEXT, notes TEXT, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS partner_accounts (id INTEGER PRIMARY KEY, partner_name TEXT, transaction_type TEXT, amount NUMERIC, date TEXT, notes TEXT, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS supplier_returns (id INTEGER PRIMARY KEY, supplier_id INTEGER, supplier TEXT, return_date TEXT, total NUMERIC, notes TEXT, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS supplier_return_items (id INTEGER PRIMARY KEY, return_id INTEGER, product_id INTEGER, product_name TEXT, quantity NUMERIC, unit_price NUMERIC, subtotal NUMERIC, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS held_carts (id INTEGER PRIMARY KEY, created_at TEXT, cart_data TEXT, notes TEXT, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS inventories (id INTEGER PRIMARY KEY, date TEXT, status TEXT, notes TEXT, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS inventory_items (id INTEGER PRIMARY KEY, inventory_id INTEGER, product_id INTEGER, expected_qty NUMERIC, actual_qty NUMERIC, diff_qty NUMERIC, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS caisse_ouverture (id INTEGER PRIMARY KEY, date TEXT, montant_initial NUMERIC, notes TEXT, created_at TEXT, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY, expense_date TEXT, category TEXT, amount NUMERIC, notes TEXT, created_at TEXT, sync_status INTEGER, cloud_id INTEGER, updated_at TEXT);
    """
    try:
        conn = get_connection()
        c = conn.cursor()
        for q in schema.split(";"):
            if q.strip():
                c.execute(q)
        conn.commit()
        conn.close()
        print("Schema initialized!")
    except Exception as e:
        print(f"Schema init error: {e}")

@api_app.on_event("startup")
def startup_event():
    init_db()


# Enable CORS for local Wi-Fi and remote tunnels
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_local_ip() -> str:
    """Detect local IPv4 address on Wi-Fi/LAN reliably."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass

    try:
        host_name = socket.gethostname()
        for ip in socket.gethostbyname_ex(host_name)[2]:
            if not ip.startswith("127.") and (ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172.")):
                return ip
    except Exception:
        pass

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ══════════════════════════════════════════════════════════════════
# REST API ENDPOINTS
# ══════════════════════════════════════════════════════════════════

@api_app.get("/api/health")
def api_health():
    return {"status": "ok", "app": "PeintPro", "version": "1.0", "local_ip": get_local_ip()}


@api_app.get("/api/dashboard")
def api_dashboard():
    try:
        conn = get_connection()
        c = conn.cursor()
        from datetime import datetime
        today_str = datetime.now().strftime("%Y-%m-%d")

        # Today sales
        c.execute("""
            SELECT COALESCE(SUM(total - remise), 0), COALESCE(SUM(preparation_total), 0) 
            FROM sales WHERE substr(sale_date, 1, 10) = ?
        """, (today_str,))
        row = c.fetchone()
        today_prod = float(row[0] or 0)
        today_prep = float(row[1] or 0)

        # Encaissement cash today
        exec_query(c, "SELECT COALESCE(SUM(grand_total), 0) FROM sales WHERE is_debt = 0 AND substr(sale_date, 1, 10) = ?", (today_str,))
        checkout_cash = float(list(c.fetchone().values())[0] or 0)

        exec_query(c, "SELECT COALESCE(SUM(versement_total), 0) FROM sales WHERE is_debt = 1 AND substr(sale_date, 1, 10) = ?", (today_str,))
        init_versement = float(list(c.fetchone().values())[0] or 0)

        c.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM debt_payments
            WHERE substr(payment_date, 1, 10) = ?
        """, (today_str,))
        client_reglements = float(list(c.fetchone().values())[0] or 0)

        exec_query(c, "SELECT COALESCE(SUM(amount), 0) FROM supplier_payments WHERE substr(payment_date, 1, 10) = ?", (today_str,))
        achats_paid = float(list(c.fetchone().values())[0] or 0)

        net_encaissement = (checkout_cash + init_versement + client_reglements) - achats_paid

        # Total outstanding debts
        exec_query(c, "SELECT COALESCE(SUM(remaining), 0) FROM debts WHERE status != 'paye'")
        total_client_debts = float(list(c.fetchone().values())[0] or 0)

        # Low stock count
        exec_query(c, "SELECT COUNT(*) FROM products WHERE active = 1 AND stock_qty <= 5")
        low_stock_count = int(list(c.fetchone().values())[0] or 0)

        conn.close()
        return {
            "today_sales": today_prod + today_prep,
            "today_sales_formatted": fmt_price(today_prod + today_prep),
            "net_encaissement": net_encaissement,
            "net_encaissement_formatted": fmt_price(net_encaissement),
            "client_debts": total_client_debts,
            "client_debts_formatted": fmt_price(total_client_debts),
            "low_stock_count": low_stock_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_app.get("/api/products")
def api_get_products(search: Optional[str] = None):
    try:
        conn = get_connection()
        c = conn.cursor()
        if search:
            q = f"%{search.strip()}%"
            c.execute("""
                SELECT p.*, c.name as category_name
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.active = 1 AND (LOWER(p.name) LIKE LOWER(?) OR LOWER(p.barcode) LIKE LOWER(?))
                ORDER BY p.name
            """, (q, q))
        else:
            c.execute("""
                SELECT p.*, c.name as category_name
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.active = 1
                ORDER BY p.name
            """)
        products = [dict(r) for r in c.fetchall()]
        conn.close()
        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_app.post("/api/products/update_stock")
def api_update_product_stock(data: Dict[str, Any] = Body(...)):
    try:
        product_id = int(data.get("product_id", 0))
        new_qty = float(data.get("stock_qty", 0))
        sell_price = data.get("sell_price")
        buy_price = data.get("buy_price")

        if not product_id:
            raise HTTPException(status_code=400, detail="Missing product_id")

        conn = get_connection()
        c = conn.cursor()

        if sell_price is not None and buy_price is not None:
            c.execute("""
                UPDATE products 
                SET stock_qty = ?, sell_price = ?, buy_price = ?
                WHERE id = ?
            """, (new_qty, float(sell_price), float(buy_price), product_id))
        else:
            exec_query(c, "UPDATE products SET stock_qty = ? WHERE id = ?", (new_qty, product_id))

        conn.commit()
        conn.close()

        pass # No GUI signals in cloud
        return {"status": "success", "message": "Stock mis à jour !"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_app.get("/api/sales")
def api_get_sales(limit: int = 30):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT s.*, IFNULL(d.remaining, 0) as debt_remaining
            FROM sales s
            LEFT JOIN debts d ON s.id = d.sale_id
            ORDER BY s.id DESC
            LIMIT ?
        """, (limit,))
        sales = [dict(r) for r in c.fetchall()]
        conn.close()
        return sales
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_app.post("/api/sales/create")
def api_create_sale(data: Dict[str, Any] = Body(...)):
    try:
        items = data.get("items", [])
        if not items:
            raise HTTPException(status_code=400, detail="Aucun article sélectionné")

        client_id = data.get("client_id")
        client_name = data.get("client_name") or "Client Passager"
        is_debt = 1 if data.get("is_debt") else 0
        versement = float(data.get("versement_total", 0) or 0)
        remise = float(data.get("remise", 0) or 0)
        payment_method = data.get("payment_method") or "Espèces"
        notes = data.get("notes") or ""

        conn = get_connection()
        c = conn.cursor()

        total = sum(float(i["quantity"]) * float(i["unit_price"]) for i in items)
        grand_total = max(0.0, total - remise)

        c.execute("""
            INSERT INTO sales (total, grand_total, remise, versement_total, client_id, client_name, is_debt, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (total, grand_total, remise, versement, client_id, client_name, is_debt, payment_method, notes))
        sale_id = c.lastrowid

        for item in items:
            pid = item["product_id"]
            qty = float(item["quantity"])
            uprice = float(item["unit_price"])
            utype = item.get("unit_type", "PCS")
            subtotal = qty * uprice

            c.execute("""
                SELECT buy_price, buy_price_per_kg FROM products WHERE id = ?
            """, (pid,))
            cost_row = c.fetchone()
            cost_price = float((cost_row["buy_price_per_kg"] if utype == "KG" else cost_row["buy_price"]) or 0) if cost_row else 0.0

            c.execute("""
                INSERT INTO sale_items (sale_id, product_id, product_name, unit_type, quantity, unit_price, unit_cost_price, subtotal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (sale_id, pid, item["product_name"], utype, qty, uprice, cost_price, subtotal))

            if utype == "PCS":
                exec_query(c, "UPDATE products SET stock_qty = MAX(0, stock_qty - ?) WHERE id = ?", (qty, pid))
            else:
                exec_query(c, "UPDATE products SET open_bidon_kg = MAX(0, open_bidon_kg - ?) WHERE id = ?", (qty, pid))

        if is_debt:
            rem_debt = max(0.0, grand_total - versement)
            status = 'paye' if rem_debt <= 0.01 else ('partiel' if versement > 0 else 'impaye')
            c.execute("""
                INSERT INTO debts (client_id, client_name, sale_id, amount, paid, remaining, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (client_id, client_name, sale_id, grand_total, versement, rem_debt, status))

        conn.commit()
        conn.close()

        pass # No GUI signals in cloud
        pass # No GUI signals in cloud
        return {"status": "success", "sale_id": sale_id, "grand_total": grand_total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_app.post("/api/sales/devis")
def api_create_devis(data: Dict[str, Any] = Body(...)):
    try:
        items = data.get("items", [])
        if not items:
            raise HTTPException(status_code=400, detail="Aucun article sélectionné")
            
        client_name = data.get("client_name") or "Client Passager"
        remise = float(data.get("remise", 0) or 0)
        
        from services.invoice_pdf import generate_devis_pdf
        import os
        
        pdf_path = os.path.join(os.getcwd(), "data", "devis_web.pdf")
        generate_devis_pdf(items, client_name=client_name, total_remise=remise, output_path=pdf_path)
        
        return FileResponse(pdf_path, media_type="application/pdf", filename=f"Devis_{client_name}.pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/api/clients")
def api_get_clients():
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT c.*, 
                   (SELECT IFNULL(SUM(remaining), 0) FROM debts WHERE client_id = c.id AND status != 'paye') as total_debt
            FROM clients c
            ORDER BY c.name
        """)
        clients = [dict(r) for r in c.fetchall()]
        conn.close()
        return clients
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_app.get("/api/suppliers")
def api_get_suppliers():
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT s.*, 
                (SELECT IFNULL(SUM(total), 0) FROM purchases WHERE supplier_id = s.id) as total_purchases,
                (SELECT IFNULL(SUM(amount), 0) FROM supplier_payments WHERE supplier_id = s.id) as total_payments,
                (SELECT IFNULL(SUM(total), 0) FROM supplier_returns WHERE supplier_id = s.id) as total_returns
            FROM suppliers s
            ORDER BY s.name
        """)
        suppliers = [dict(r) for r in c.fetchall()]
        for s in suppliers:
            s["net_debt"] = s["initial_debt"] + s["total_purchases"] - s["total_payments"] - s["total_returns"]
        conn.close()
        return suppliers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_app.post("/api/versements/client")
def api_record_client_versement(data: Dict[str, Any] = Body(...)):
    try:
        client_id = data.get("client_id")
        amount = float(data.get("amount", 0))
        notes = data.get("notes", "")

        if not amount or amount <= 0:
            raise HTTPException(status_code=400, detail="Montant invalide")

        conn = get_connection()
        c = conn.cursor()

        c.execute("""
            INSERT INTO transactions_log (date, type, description, amount)
            VALUES (datetime('now','localtime'), 'Versement Dette', ?, ?)
        """, (f"Versement Client ID #{client_id} ({notes})", amount))

        c.execute("""
            SELECT id, remaining, paid FROM debts 
            WHERE client_id = ? AND status != 'paye' 
            ORDER BY id ASC
        """, (client_id,))
        debts = c.fetchall()

        rem_pay = amount
        for d in debts:
            did = d["id"]
            drem = float(d["remaining"] or 0)
            dpaid = float(d["paid"] or 0)

            if rem_pay <= 0:
                break

            pay_part = min(rem_pay, drem)
            new_rem = drem - pay_part
            new_paid = dpaid + pay_part
            new_status = 'paye' if new_rem <= 0.01 else 'partiel'

            exec_query(c, "UPDATE debts SET remaining = ?, paid = ?, status = ? WHERE id = ?", (new_rem, new_paid, new_status, did))
            exec_query(c, "INSERT INTO debt_payments (debt_id, amount) VALUES (?, ?)", (did, pay_part))
            rem_pay -= pay_part

        conn.commit()
        conn.close()

        pass # No GUI signals in cloud
        return {"status": "success", "message": "Versement enregistré !"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_app.post("/api/versements/supplier")
def api_record_supplier_versement(data: Dict[str, Any] = Body(...)):
    try:
        supplier_id = data.get("supplier_id")
        amount = float(data.get("amount", 0))
        notes = data.get("notes", "")

        if not supplier_id or amount <= 0:
            raise HTTPException(status_code=400, detail="Données invalides")

        conn = get_connection()
        c = conn.cursor()

        c.execute("""
            INSERT INTO supplier_payments (supplier_id, amount, payment_date, notes)
            VALUES (?, ?, datetime('now','localtime'), ?)
        """, (supplier_id, amount, notes))

        conn.commit()
        conn.close()

        pass # No GUI signals in cloud
        return {"status": "success", "message": "Versement fournisseur enregistré !"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════
# REPORTS & INSIGHTS ENDPOINTS (Read-Only Analytics)
# ══════════════════════════════════════════════════════════════════

@api_app.get("/api/reports")
def api_reports(period: str = "today", date_from: Optional[str] = None, date_to: Optional[str] = None):
    """Full financial KPI report with period filtering — mirrors reports_screen.py logic exactly."""
    try:
        from datetime import datetime, timedelta
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")

        if period == "today":
            d_from = d_to = today_str
        elif period == "week":
            monday = today - timedelta(days=today.weekday())
            d_from = monday.strftime("%Y-%m-%d")
            d_to = today_str
        elif period == "month":
            d_from = today.strftime("%Y-%m-01")
            d_to = today_str
        elif period == "custom" and date_from and date_to:
            d_from = date_from
            d_to = date_to
        elif period == "all":
            d_from = "2020-01-01"
            d_to = today_str
        else:
            d_from = d_to = today_str

        conn = get_connection()
        c = conn.cursor()

        # CA Brut (excluding returns)
        c.execute("""
            SELECT COALESCE(SUM(grand_total), 0), COUNT(*),
                   COALESCE(SUM(preparation_total), 0)
            FROM sales
            WHERE substr(sale_date, 1, 10) >= ? AND substr(sale_date, 1, 10) <= ?
              AND payment_method != 'Retour' AND grand_total >= 0
        """, (d_from, d_to))
        row = c.fetchone()
        revenue = float(row[0] or 0)
        sale_count = int(row[1] or 0)
        prep_revenue = float(row[2] or 0)

        # Client returns
        c.execute("""
            SELECT COALESCE(SUM(ABS(grand_total)), 0) FROM sales
            WHERE payment_method = 'Retour' AND grand_total < 0
              AND substr(sale_date, 1, 10) >= ? AND substr(sale_date, 1, 10) <= ?
        """, (d_from, d_to))
        client_returns = float(list(c.fetchone().values())[0] or 0)
        revenue_net = revenue - client_returns

        # Purchases
        c.execute("""
            SELECT COALESCE(SUM(total), 0) FROM purchases
            WHERE substr(purchase_date, 1, 10) >= ? AND substr(purchase_date, 1, 10) <= ?
        """, (d_from, d_to))
        purchases_total = float(list(c.fetchone().values())[0] or 0)

        c.execute("""
            SELECT COALESCE(SUM(total), 0) FROM supplier_returns
            WHERE substr(return_date, 1, 10) >= ? AND substr(return_date, 1, 10) <= ?
        """, (d_from, d_to))
        supplier_returns_total = float(list(c.fetchone().values())[0] or 0)
        purchases_net = purchases_total - supplier_returns_total

        # Profit = margin + teinte - remises
        c.execute("""
            SELECT COALESCE(SUM(
                (si.unit_price -
                    CASE
                        WHEN si.unit_cost_price > 0 THEN si.unit_cost_price
                        WHEN p.buy_price > 0 AND si.unit_type = 'PCS' THEN p.buy_price
                        WHEN p.buy_price_per_kg > 0 AND si.unit_type = 'KG' THEN p.buy_price_per_kg
                        ELSE 0.0
                    END
                ) * si.quantity
            ), 0)
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            LEFT JOIN products p ON si.product_id = p.id
            WHERE substr(s.sale_date, 1, 10) >= ? AND substr(s.sale_date, 1, 10) <= ?
              AND s.grand_total >= 0 AND s.payment_method != 'Retour'
        """, (d_from, d_to))
        margin_profit = float(list(c.fetchone().values())[0] or 0.0)

        c.execute("""
            SELECT COALESCE(SUM(remise), 0), COALESCE(SUM(preparation_total), 0)
            FROM sales
            WHERE substr(sale_date, 1, 10) >= ? AND substr(sale_date, 1, 10) <= ?
              AND grand_total >= 0 AND payment_method != 'Retour'
        """, (d_from, d_to))
        row_rp = c.fetchone()
        total_remises = float(list(row_rp.values())[0] or 0.0)
        total_prep_profit = float(list(row_rp.values())[1] or 0.0)
        profit = max(0.0, margin_profit + total_prep_profit - total_remises)

        # Encaissements
        c.execute("""
            SELECT COALESCE(SUM(grand_total), 0) FROM sales
            WHERE is_debt = 0 AND payment_method != 'Retour' AND grand_total >= 0
              AND substr(sale_date, 1, 10) >= ? AND substr(sale_date, 1, 10) <= ?
        """, (d_from, d_to))
        cash_sales = float(list(c.fetchone().values())[0] or 0)

        c.execute("""
            SELECT COALESCE(SUM(versement_total), 0) FROM sales
            WHERE is_debt = 1 AND versement_total > 0 AND grand_total >= 0
              AND substr(sale_date, 1, 10) >= ? AND substr(sale_date, 1, 10) <= ?
        """, (d_from, d_to))
        initial_versements = float(list(c.fetchone().values())[0] or 0)

        c.execute("""
            SELECT COALESCE(SUM(dp.amount), 0) FROM debt_payments dp
            WHERE substr(dp.payment_date, 1, 10) >= ? AND substr(dp.payment_date, 1, 10) <= ?
        """, (d_from, d_to))
        post_reglements = float(list(c.fetchone().values())[0] or 0)

        c.execute("""
            SELECT COALESCE(SUM(ABS(grand_total)), 0) FROM sales
            WHERE payment_method = 'Retour' AND grand_total < 0
              AND substr(sale_date, 1, 10) >= ? AND substr(sale_date, 1, 10) <= ?
        """, (d_from, d_to))
        client_returns_refunded = float(list(c.fetchone().values())[0] or 0)

        c.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM expenses
            WHERE substr(expense_date, 1, 10) >= ? AND substr(expense_date, 1, 10) <= ?
        """, (d_from, d_to))
        expenses_total = float(list(c.fetchone().values())[0] or 0)

        total_encaissements = cash_sales + initial_versements + post_reglements - client_returns_refunded - expenses_total

        c.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM supplier_payments
            WHERE substr(payment_date, 1, 10) >= ? AND substr(payment_date, 1, 10) <= ?
        """, (d_from, d_to))
        supplier_payments_out = float(list(c.fetchone().values())[0] or 0)

        tresorerie_nette = total_encaissements - supplier_payments_out

        # Top 10 products
        c.execute("""
            SELECT si.product_name, SUM(si.quantity) as total_qty, SUM(si.subtotal) as total_revenue
            FROM sale_items si JOIN sales s ON si.sale_id = s.id
            WHERE substr(s.sale_date, 1, 10) >= ? AND substr(s.sale_date, 1, 10) <= ?
            GROUP BY si.product_name ORDER BY total_qty DESC LIMIT 10
        """, (d_from, d_to))
        top_products = [{"name": r["product_name"], "qty": r["total_qty"], "revenue": r["total_revenue"]} for r in c.fetchall()]

        conn.close()

        return {
            "period": period, "date_from": d_from, "date_to": d_to,
            "revenue_net": revenue_net, "revenue_net_fmt": fmt_price(revenue_net),
            "prep_revenue": prep_revenue,
            "client_returns": client_returns,
            "purchases_net": purchases_net, "purchases_net_fmt": fmt_price(purchases_net),
            "purchases_brut": purchases_total, "supplier_returns": supplier_returns_total,
            "profit": profit, "profit_fmt": fmt_price(profit),
            "margin_profit": margin_profit, "total_prep_profit": total_prep_profit, "total_remises": total_remises,
            "sale_count": sale_count,
            "cash_sales": cash_sales, "initial_versements": initial_versements,
            "post_reglements": post_reglements, "client_returns_refunded": client_returns_refunded,
            "expenses": expenses_total,
            "total_encaissements": total_encaissements, "total_encaissements_fmt": fmt_price(total_encaissements),
            "supplier_payments_out": supplier_payments_out,
            "tresorerie_nette": tresorerie_nette, "tresorerie_nette_fmt": fmt_price(tresorerie_nette),
            "top_products": top_products
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_app.get("/api/insights/suppliers")
def api_insights_suppliers():
    """Enriched supplier insights: purchases, debt, payment history."""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT s.*,
                (SELECT IFNULL(SUM(total), 0) FROM purchases WHERE supplier_id = s.id) as total_purchases,
                (SELECT IFNULL(SUM(amount), 0) FROM supplier_payments WHERE supplier_id = s.id) as total_payments,
                (SELECT IFNULL(SUM(total), 0) FROM supplier_returns WHERE supplier_id = s.id) as total_returns
            FROM suppliers s ORDER BY s.name
        """)
        suppliers = []
        for row in c.fetchall():
            s = dict(row)
            s["net_debt"] = s["initial_debt"] + s["total_purchases"] - s["total_payments"] - s["total_returns"]
            # Last 10 payments
            c.execute("""
                SELECT id, amount, payment_date, notes FROM supplier_payments
                WHERE supplier_id = ? ORDER BY id DESC LIMIT 10
            """, (s["id"],))
            s["recent_payments"] = [dict(p) for p in c.fetchall()]
            # Last 10 purchases
            c.execute("""
                SELECT id, purchase_date, total, notes FROM purchases
                WHERE supplier_id = ? ORDER BY id DESC LIMIT 10
            """, (s["id"],))
            s["recent_purchases"] = [dict(p) for p in c.fetchall()]
            suppliers.append(s)
        conn.close()
        return suppliers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_app.get("/api/insights/clients")
def api_insights_clients():
    """Enriched client insights: total purchased, debt, payment history, ranking."""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT c.*,
                (SELECT IFNULL(SUM(remaining), 0) FROM debts WHERE client_id = c.id AND status != 'paye') as total_debt,
                (SELECT IFNULL(SUM(grand_total), 0) FROM sales WHERE client_id = c.id AND grand_total >= 0 AND payment_method != 'Retour') as total_purchased,
                (SELECT COUNT(*) FROM sales WHERE client_id = c.id AND grand_total >= 0 AND payment_method != 'Retour') as sale_count
            FROM clients c ORDER BY total_purchased DESC
        """)
        clients = []
        for row in c.fetchall():
            cl = dict(row)
            # Last 10 debt payments
            c.execute("""
                SELECT dp.id, dp.amount, dp.payment_date, d.sale_id
                FROM debt_payments dp
                JOIN debts d ON dp.debt_id = d.id
                WHERE d.client_id = ?
                ORDER BY dp.id DESC LIMIT 10
            """, (cl["id"],))
            cl["recent_payments"] = [dict(p) for p in c.fetchall()]
            # Active debts
            c.execute("""
                SELECT id, sale_id, amount, paid, remaining, status, created_at
                FROM debts WHERE client_id = ? AND status != 'paye'
                ORDER BY id DESC
            """, (cl["id"],))
            cl["active_debts"] = [dict(d) for d in c.fetchall()]
            clients.append(cl)
        conn.close()
        return clients
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_app.get("/api/inventories")
def api_get_inventories():
    """List all inventory sessions with summary stats."""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT inv.id, inv.date, inv.status, inv.notes,
                (SELECT COUNT(*) FROM inventory_items WHERE inventory_id = inv.id) as item_count,
                (SELECT IFNULL(SUM(ABS(diff_qty)), 0) FROM inventory_items WHERE inventory_id = inv.id) as total_abs_diff
            FROM inventories inv ORDER BY inv.id DESC
        """)
        inventories = [dict(r) for r in c.fetchall()]
        conn.close()
        return inventories
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_app.get("/api/inventories/{inv_id}")
def api_get_inventory_detail(inv_id: int):
    """Detail line-by-line for a single inventory session."""
    try:
        conn = get_connection()
        c = conn.cursor()
        exec_query(c, "SELECT * FROM inventories WHERE id = ?", (inv_id,))
        inv = c.fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Inventaire introuvable")

        c.execute("""
            SELECT ii.id, ii.product_id, p.name as product_name,
                   ii.expected_qty, ii.actual_qty, ii.diff_qty,
                   COALESCE(p.buy_price, 0) as unit_cost
            FROM inventory_items ii
            LEFT JOIN products p ON ii.product_id = p.id
            WHERE ii.inventory_id = ?
            ORDER BY ABS(ii.diff_qty) DESC
        """, (inv_id,))
        items = []
        for r in c.fetchall():
            item = dict(r)
            item["ecart_valeur"] = item["diff_qty"] * item["unit_cost"]
            items.append(item)

        total_ecart_valeur = sum(i["ecart_valeur"] for i in items)
        conn.close()
        return {
            "inventory": dict(inv),
            "items": items,
            "total_ecart_valeur": total_ecart_valeur
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_app.get("/api/inventories/compare")
def api_compare_inventories(id1: int = 0, id2: int = 0):
    """Compare stock evolution between two inventory sessions."""
    try:
        if not id1 or not id2:
            raise HTTPException(status_code=400, detail="Paramètres id1 et id2 requis")

        conn = get_connection()
        c = conn.cursor()

        # Get items from both inventories
        c.execute("""
            SELECT ii.product_id, p.name as product_name,
                   ii.expected_qty, ii.actual_qty, ii.diff_qty
            FROM inventory_items ii
            LEFT JOIN products p ON ii.product_id = p.id
            WHERE ii.inventory_id = ?
        """, (id1,))
        items_1 = {r["product_id"]: dict(r) for r in c.fetchall()}

        c.execute("""
            SELECT ii.product_id, p.name as product_name,
                   ii.expected_qty, ii.actual_qty, ii.diff_qty
            FROM inventory_items ii
            LEFT JOIN products p ON ii.product_id = p.id
            WHERE ii.inventory_id = ?
        """, (id2,))
        items_2 = {r["product_id"]: dict(r) for r in c.fetchall()}

        # Merge and compute evolution
        all_pids = set(list(items_1.keys()) + list(items_2.keys()))
        comparison = []
        for pid in all_pids:
            i1 = items_1.get(pid, {})
            i2 = items_2.get(pid, {})
            name = i1.get("product_name") or i2.get("product_name") or f"Produit #{pid}"
            qty1 = i1.get("actual_qty", 0)
            qty2 = i2.get("actual_qty", 0)
            diff1 = i1.get("diff_qty", 0)
            diff2 = i2.get("diff_qty", 0)
            comparison.append({
                "product_id": pid,
                "product_name": name,
                "inv1_actual": qty1,
                "inv1_diff": diff1,
                "inv2_actual": qty2,
                "inv2_diff": diff2,
                "evolution": qty2 - qty1
            })

        comparison.sort(key=lambda x: abs(x["evolution"]), reverse=True)

        # Session metadata
        exec_query(c, "SELECT id, date, status FROM inventories WHERE id IN (?, ?)", (id1, id2))
        sessions = [dict(r) for r in c.fetchall()]

        conn.close()
        return {
            "sessions": sessions,
            "comparison": comparison
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@api_app.post("/api/sync/receive")
def api_sync_receive(payload: Dict[str, List[Dict[str, Any]]] = Body(...)):
    try:
        conn = get_connection()
        c = conn.cursor()
        
        for table, rows in payload.items():
            if not rows: continue
            
            # Simple UPSERT for PostgreSQL (requires PK 'id' constraint)
            cols = list(rows[0].keys())
            cols_str = ", ".join(cols)
            val_placeholders = ", ".join(["%s"] * len(cols))
            update_str = ", ".join([f"{col}=EXCLUDED.{col}" for col in cols if col != 'id'])
            
            query = f"INSERT INTO {table} ({cols_str}) VALUES ({val_placeholders}) ON CONFLICT (id) DO UPDATE SET {update_str}"
            
            for row in rows:
                c.execute(query, [row[col] for col in cols])
                
        conn.commit()
        conn.close()
        return {"status": "ok", "synced_tables": list(payload.keys())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════
# STATIC FILE SERVING FOR PWA (web_mobile)
# ══════════════════════════════════════════════════════════════════

# Resolve web_mobile path: works both in development and PyInstaller EXE
_base_dir = os.path.dirname(os.path.abspath(__file__))
web_dir = os.path.join(_base_dir, "web_mobile")
os.makedirs(web_dir, exist_ok=True)

# Mount web_mobile as /static AND serve individual files at root
api_app.mount("/static", StaticFiles(directory=web_dir), name="static")


@api_app.get("/")
@api_app.get("/index.html")
@api_app.get("/static/index.html")
def read_root():
    index_path = os.path.join(web_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return JSONResponse({"status": "PeintPro API Server Running — web_mobile/index.html not found", "web_dir": web_dir})


@api_app.get("/sw.js")
def serve_sw():
    """Service worker must be served from root scope for iOS PWA."""
    sw_path = os.path.join(web_dir, "sw.js")
    if os.path.exists(sw_path):
        return FileResponse(sw_path, media_type="application/javascript")
    return JSONResponse({"error": "sw.js not found"})


@api_app.get("/manifest.json")
def serve_manifest():
    manifest_path = os.path.join(web_dir, "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path, media_type="application/json")
    return JSONResponse({"error": "manifest.json not found"})


# Server runner background thread
_server_thread: Optional[threading.Thread] = None


def start_mobile_api_server(host: str = "0.0.0.0", port: int = 8000):
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        logger.info("[MobileAPI] Server is already running.")
        return

    def run():
        logger.info(f"[MobileAPI] Starting background FastAPI server on {host}:{port}...")
        uvicorn.run(api_app, host=host, port=port, log_level="error")

    _server_thread = threading.Thread(target=run, daemon=True)
    _server_thread.start()
    logger.info(f"[MobileAPI] Background thread launched on http://{get_local_ip()}:{port}")
