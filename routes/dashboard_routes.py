from flask import Blueprint, render_template, redirect, url_for, session, flash
from models import User

dashboard_bp = Blueprint('dashboard', __name__)  # blueprint name used in url_for()

# ------------------------
# FACTORY DASHBOARD VIEW
# ------------------------
@dashboard_bp.route('/dashboard', endpoint='dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('auth.index'))

    user = User.query.get(session['user_id'])

    if not user or not user.factory:
        flash('No factory linked to this user.', 'error')
        return redirect(url_for('auth.index'))

    factory = user.factory

    # Make sure factory.products is accessible (should be defined in the model)
    total_products = len(factory.products)
    total_orders = len(factory.orders)
    total_revenue = sum(order.total_price for order in factory.orders)

    recent_orders = factory.orders[-5:]  # last 5 orders
    low_stock_products = [p for p in factory.products if p.quantity < 10]

    return render_template(
        'dashboard.html',
        user=user,
        total_products=total_products,
        total_orders=total_orders,
        total_revenue=total_revenue,
        recent_orders=recent_orders,
        low_stock_products=low_stock_products
    )

# ------------------------
# SELLER SHOP VIEW
# ------------------------
@dashboard_bp.route('/shop', endpoint='shop')
def shop():
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('auth.index'))

    user = User.query.get(session['user_id'])
    if user.role != 'seller':
        flash('Access denied: Only sellers can access the shop.', 'error')
        return redirect(url_for('auth.index'))

    return render_template('shop.html', user=user)

# ------------------------
# PRODUCT MANAGEMENT VIEW (FACTORY)
# ------------------------
@dashboard_bp.route('/products', endpoint='products')
def products():
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('auth.index'))

    user = User.query.get(session['user_id'])

    if not user or not user.factory:
        flash('No factory linked to this user.', 'error')
        return redirect(url_for('auth.index'))

    factory = user.factory
    return render_template('products.html', user=user, products=factory.products)

@dashboard_bp.route('/orders', endpoint='orders')
def orders():
    return render_template('orders.html')  # Create a basic orders.html file

@dashboard_bp.route('/analytics', endpoint='analytics')
def analytics():
    return render_template('analytics.html')  # Create analytics.html
