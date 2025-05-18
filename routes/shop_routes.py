from datetime import datetime
from flask import Blueprint, current_app, render_template, request, session, redirect, url_for, flash
from models import Receipt, User, Product, Category, Factory, db, Order, OrderItem

shop_bp = Blueprint('shop', __name__)

# ---------------- Helpers ----------------
def seller_required():
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return False, redirect(url_for('auth.index'))
    user = User.query.get(session['user_id'])
    if not user or user.role != 'seller':
        flash('Unauthorized access.', 'error')
        return False, redirect(url_for('auth.index'))
    return True, user

def ensure_cart():
    if 'cart' not in session or not isinstance(session['cart'], dict):
        session['cart'] = {}

# ---------------- Browse Products ----------------
@shop_bp.route('/shop')
def browse():
    ok, resp = seller_required()
    if not ok:
        return resp

    ensure_cart()
    user = resp
    selected_category = request.args.get('category', type=int)
    selected_factory = request.args.get('factory', type=int)

    categories = Category.query.all()
    factories = Factory.query.all()

    query = Product.query
    if selected_category:
        query = query.join(Factory).filter(Factory.category_id == selected_category)
    if selected_factory:
        query = query.filter(Product.factory_id == selected_factory)

    products = query.all()
    cart_quantity = sum(session['cart'].values())

    return render_template(
        'shop/browse.html',
        user=user,
        categories=categories,
        factories=factories,
        products=products,
        selected_category=selected_category,
        selected_factory=selected_factory,
        now=datetime.utcnow,
        cart_quantity=cart_quantity
    )

# ---------------- View Cart ----------------
@shop_bp.route('/cart')
def cart():
    ok, resp = seller_required()
    if not ok:
        return resp

    ensure_cart()
    user = resp
    cart = session['cart']
    product_ids = list(cart.keys())
    products = Product.query.filter(Product.id.in_(product_ids)).all()
    product_map = {p.id: p for p in products}

    cart_items = []
    total_price = 0
    for pid_str, qty in cart.items():
        pid = int(pid_str)
        product = product_map.get(pid)
        if product:
            subtotal = product.price * qty
            total_price += subtotal
            cart_items.append({
                'product': product,
                'quantity': qty,
                'subtotal': subtotal
            })

    return render_template(
        'shop/cart.html',
        user=user,
        cart_items=cart_items,
        total_price=total_price,
        now=datetime.utcnow,
        cart_quantity=sum(cart.values())
    )

# ---------------- Add to Cart ----------------
@shop_bp.route('/cart/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    ok, resp = seller_required()
    if not ok:
        return resp

    ensure_cart()
    product = Product.query.get_or_404(product_id)
    cart = session['cart']
    current_qty = cart.get(str(product_id), 0)

    if current_qty < product.quantity:
        cart[str(product_id)] = current_qty + 1
        session['cart'] = cart
        flash(f'Added {product.name} to cart.', 'success')
    else:
        flash(f'Only {product.quantity} units available for {product.name}.', 'error')

    return redirect(request.referrer or url_for('shop.browse'))

# ---------------- Update Cart Quantity (+ / -) ----------------
@shop_bp.route('/cart/update/<int:product_id>/<string:action>', methods=['POST'])
def update_cart_quantity(product_id, action):
    ok, resp = seller_required()
    if not ok:
        return resp

    ensure_cart()
    cart = session['cart']
    pid = str(product_id)

    product = Product.query.get_or_404(product_id)

    if pid not in cart:
        flash("Product not in cart.", "error")
        return redirect(url_for('shop.cart'))

    if action == 'increment':
        if cart[pid] < product.quantity:
            cart[pid] += 1
        else:
            flash("Cannot exceed available stock.", "warning")

    elif action == 'decrement':
        if cart[pid] > 1:
            cart[pid] -= 1
        elif cart[pid] == 1:
            del cart[pid]
            flash(f"{product.name} removed from cart.", "info")
        else:
            flash("Quantity can't be less than 0.", "warning")

    else:
        flash("Invalid action.", "error")

    session['cart'] = cart
    return redirect(url_for('shop.cart'))

# ---------------- Remove from Cart ----------------
@shop_bp.route('/cart/remove/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    ok, resp = seller_required()
    if not ok:
        return resp

    ensure_cart()
    cart = session['cart']
    if str(product_id) in cart:
        del cart[str(product_id)]
        session['cart'] = cart
        flash('Item removed from cart.', 'success')
    else:
        flash('Item not found in cart.', 'error')
    return redirect(url_for('shop.cart'))

# ---------------- View Orders ----------------
@shop_bp.route('/my-orders', endpoint='orders')
def orders():
    ok, resp = seller_required()
    if not ok:
        return resp

    user = resp
    orders = Order.query.filter_by(seller_id=user.id).order_by(Order.order_date.desc()).all()
    return render_template(
        'shop/customers_orders.html',
        user=user,
        orders=orders,
        now=datetime.utcnow
    )

# ---------------- Place Order ----------------
@shop_bp.route('/orders/place', methods=['POST'])
def place_order():
    ok, resp = seller_required()
    if not ok:
        return resp

    ensure_cart()
    user = resp
    cart = session['cart']
    if not cart:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('shop.cart'))

    payment_method = request.form.get('payment_method')
    shipping_address = request.form.get('shipping_address')

    if not payment_method:
        flash('Please select a payment method.', 'error')
        return redirect(url_for('shop.cart'))

    product_ids = list(map(int, cart.keys()))
    products = Product.query.filter(Product.id.in_(product_ids)).all()
    product_map = {p.id: p for p in products}

    factory_ids = {product_map[pid].factory_id for pid in product_ids}
    if len(factory_ids) != 1:
        flash('Order contains products from multiple factories, which is not supported yet.', 'error')
        return redirect(url_for('shop.cart'))
    factory_id = factory_ids.pop()

    total_price = sum(product_map[int(pid)].price * qty for pid, qty in cart.items())

    # Create the Order
    new_order = Order(
        seller_id=user.id,
        factory_id=factory_id,
        total_price=total_price,
        payment_method=payment_method,
        shipping_address=shipping_address,
        status='Pending'
    )
    db.session.add(new_order)
    db.session.flush()  # Flush to get new_order.id

    # Add OrderItems
    for pid_str, qty in cart.items():
        pid = int(pid_str)
        product = product_map.get(pid)
        if product:
            item = OrderItem(
                order_id=new_order.id,
                product_id=product.id,
                quantity=qty,
                unit_price=product.price
            )
            db.session.add(item)

    # Create Receipt linked to the Order
    receipt = Receipt(
        order_id=new_order.id,
        amount_paid=total_price,
        payment_method=payment_method,
        payment_date=datetime.utcnow()
    )
    db.session.add(receipt)

    db.session.commit()

    session['cart'] = {}

    flash('Order placed successfully!', 'success')
    return redirect(url_for('shop.orders'))
