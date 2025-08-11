# --------------------------------导包-------------------------------
import csv
from datetime import datetime
import io
import os
from sqlalchemy.sql import func
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import joinedload,Mapped,mapped_column,relationship
from sqlalchemy import Integer, String, Float, DateTime, ForeignKey
from werkzeug.security import generate_password_hash, check_password_hash

# ------------------------------------------------------------------

# ---------------------------创建app---------------------------------
app=Flask(__name__) # 作为主程序运行
app.secret_key = os.environ.get('SECRET_KEY','dev_key')

raw_db_url = os.environ.get('DATABASE_URL')# Get and fix DATABASE_URL for PostgreSQL on Render
if raw_db_url and raw_db_url.startswith('postgres://'):
    raw_db_url=raw_db_url.replace('postgres://','postgresql://',1)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = raw_db_url
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG','False') == 'True'

db = SQLAlchemy(app)
# ------------------------------------------------------------------

# --------------------------定义模型----------------------------------
# 店家
class Product(db.Model):  # 商品表
    __tablename__ = 'products'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # 反向关系
    order_items: Mapped[list["OrderItem"]] = relationship(
        back_populates="product", lazy="selectin"
    )


class Order(db.Model):  # 订单表
    __tablename__ = 'orders'

    id: Mapped[int] = mapped_column(primary_key=True)
    customer: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(50), default="待处理")

    # 反向关系
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", lazy="selectin"
    )


class OrderItem(db.Model):  # 订单项表（连接订单和商品）
    __tablename__ = 'order_items'

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    # 双向关系
    product: Mapped["Product"] = relationship(back_populates="order_items", lazy="joined")
    order: Mapped["Order"] = relationship(back_populates="items")


class Purchase(db.Model):  # 进货表
    __tablename__ = 'purchases'

    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    product_name: Mapped[str] = mapped_column(String(100), nullable=False)
    product_price: Mapped[float] = mapped_column(Float, nullable=False)
    product_category: Mapped[str] = mapped_column(String(50), nullable=False)
    product_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="待处理")


class Customer(db.Model):  # 顾客账号密码表
    __tablename__ = 'customers'

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
# -------------------------------------------------------------------

# ---------------------------初始化数据库------------------------------
with app.app_context():
    db.create_all()

# -------------------------------------------------------------------

# --------------------------渲染主页-----------------------------------
@app.route('/')
def index():
    return render_template('index/index.html')
# --------------------------------------------------------------------

# ------------------------------店家视图函数----------------------------
@app.route('/store_login',methods=['GET','POST'])
def store_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'zsj' and password == '123456':
            session['store_logged_in'] = True
            return redirect(url_for('store_dashboard'))
        else:
            flash('账号或密码错误，请重试')
    return render_template('store/store_login.html')

@app.route('/store_dashboard')
def store_dashboard():
    if not session.get('store_logged_in'):
        flash('请先登录')
        return redirect(url_for('store_login'))

    return render_template('store/store_dashboard.html')

@app.route('/store/module/<name>')
def store_module(name):
    if not session.get('store_logged_in'):
        flash('请先登录')
        return redirect(url_for('store_login'))
    allowed_modules = ['product','order','purchase','export']
    if name not in allowed_modules:
        abort(404)
    return redirect(url_for(name))

@app.route('/product',methods = ['GET','POST'])
def product():
    if not session.get('store_logged_in'):
        flash('请先登录')
        return redirect(url_for('store_login'))

    if request.method == 'POST':
        try:
            name = request.form.get('name')
            price = float(request.form.get('price'))
            stock = int(request.form.get('stock'))
            category = request.form.get('category').strip()

            if not name or price < 0 or stock < 0:
                flash('名称、价格和库存必须填写，价格和库存必须为正数')
                return redirect(url_for('product'))

            if Product.query.filter_by(name=name,category=category).first():
                flash('商品已存在')
                return redirect(url_for('product'))

            new_product = Product(name=name, price=price, stock=stock, category=category)
            db.session.add(new_product)
            db.session.commit()
            flash('新商品已添加')

        except Exception as e:
            db.session.rollback()
            print(e)
            flash('新商品添加失败')

        return redirect(url_for('product'))

    products = []
    pagination = None

    if request.method == 'GET':
        search = request.args.get('search','',type=str)
        page = request.args.get('page',1,type=int)
        per_page = 10

        query = Product.query
        if search:
            query = query.filter(Product.name.ilike(f'%{search}%'))

        pagination = query.order_by(Product.id).paginate(page=page, per_page=per_page, error_out=False)
        products = pagination.items

    return render_template('store/product.html',
                               products=products,pagination=pagination)

@app.route('/delete_product/<int:product_id>' , methods=['POST'])
def delete_product(product_id):
    if not session.get('store_logged_in'):
        flash('请先登录')
        return redirect(url_for('store_login'))

    product_delete = Product.query.get_or_404(product_id)
    db.session.delete(product_delete)
    db.session.commit()
    flash('该商品已删除')
    return redirect(url_for('product'))

@app.route('/order',methods = ['GET'])
def order():
    if not session.get('store_logged_in'):
        flash('请先登录')
        return redirect(url_for('store_login'))

    orders = []
    pagination = None

    if request.method == 'GET':
        search = request.args.get('search','',type=str).strip()
        page = request.args.get('page',1,type=int)
        per_page = 10

        query = Order.query.options(
            joinedload(Order.items)
            .joinedload(OrderItem.product)
            )
        if search:
            query = query.join(Order.items).join(OrderItem.product).filter(Product.name.contains(search))

        pagination = query.order_by(Order.id).paginate(page=page, per_page=per_page, error_out=False)
        orders = pagination.items

    return render_template('store/order.html',orders=orders,pagination=pagination)

@app.route('/update_order_status/<int:order_id>' , methods=['POST'])
def update_order_status(order_id):
    if not session.get('store_logged_in'):
        flash('请先登录')
        return redirect(url_for('store_login'))

    order_query = Order.query.get_or_404(order_id)
    order_query.status = request.form.get('status')
    db.session.commit()
    flash('该订单状态已更新')
    return redirect(url_for('order'))

@app.route('/delete_order/<int:order_id>' , methods=['POST'])
def delete_order(order_id):
    if not session.get('store_logged_in'):
        flash('请先登录')
        return redirect(url_for('store_login'))
    order_delete = Order.query.get_or_404(order_id)
    db.session.delete(order_delete)
    db.session.commit()
    flash('该订单已删除')
    return redirect(url_for('order'))

@app.route('/purchase',methods = ['GET','POST'])
def purchase():
   if not session.get('store_logged_in'):
      flash('请先登录')
      return redirect(url_for('store_login'))

   if request.method == 'POST':
      try:
         owner = request.form.get('owner')
         phone = request.form.get('phone')
         address = request.form.get('address')
         product_name = request.form.get('product_name')
         product_price = float(request.form.get('product_price'))
         product_category = request.form.get('product_category')
         product_quantity = int(request.form.get('product_quantity'))

         if not owner or not phone or not address or not product_name or product_price < 0.0 or not product_category or product_quantity < 0:
            flash('所有字段都必须填写，进货价格不能小于0，进货数量要为正整数')
            return redirect(url_for('purchase'))

         new_purchase = Purchase(owner=owner,phone=phone,address=address,
                                product_name=product_name,product_price=product_price,
                                product_category=product_category,product_quantity=product_quantity)
         db.session.add(new_purchase)
         db.session.commit()
         flash('进货单已创建')

      except Exception as e:
         db.session.rollback()
         print(e)
         flash('进货单创建失败')

      return redirect(url_for('purchase'))

   search = request.args.get('search','',type=str).strip()
   page = request.args.get('page',1,type=int)
   per_page = 10

   query = Purchase.query
   if search:
      query = query.filter(Purchase.product_name.ilike(f'%{search}%'))

   pagination = query.order_by(Purchase.id).paginate(page=page, per_page=per_page, error_out=False)
   purchases = pagination.items

   return render_template('store/purchase.html',
                               purchases=purchases,pagination=pagination)

@app.route('/update_purchase_status/<int:purchase_id>' , methods=['POST'])
def update_purchase_status(purchase_id):
    if not session.get('store_logged_in'):
        flash('请先登录')
        return redirect(url_for('store_login'))

    purchase_query = Purchase.query.get_or_404(purchase_id)
    purchase_query.status = request.form.get('status')
    db.session.commit()
    flash('该进货单状态已更新')
    return redirect(url_for('purchase'))

@app.route('/delete_purchase/<int:purchase_id>' , methods=['POST'])
def delete_purchase(purchase_id):
    if not session.get('store_logged_in'):
        return redirect(url_for('store_login'))
    purchase_delete = Purchase.query.get_or_404(purchase_id)
    db.session.delete(purchase_delete)
    db.session.commit()
    flash('该进货单已删除')
    return redirect(url_for('purchase'))

@app.route('/export', methods=['GET'])
def export():
    if not session.get('store_logged_in'):
        flash('请先登录')
        return redirect(url_for('store_login'))

    try:
        data_type = request.args.get('data_type')
        start_date_str = request.args.get('start_date')

        start_date = None
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            except ValueError:
                flash('日期格式错误，请重试')
                return redirect(url_for('export'))

        if not data_type:
            return render_template('store/export.html')  # 还没提交导出请求，直接渲染页面

        # 按类型查询数据，生成 CSV
        headers = None
        rows = None

        if data_type == 'product':
            query = Product.query
            if start_date:
                query = query.filter(Product.created_at >= start_date)
            products = query.all()

            headers = ['商品名称', '价格', '库存', '分类', '创建时间']
            rows = [[p.name, p.price, p.stock, p.category, p.created_at] for p in products]

        elif data_type == 'order':
            query = Order.query.options(joinedload(Order.items).joinedload(OrderItem.product))
            if start_date:
                query = query.filter(Order.created_at >= start_date)
            orders = query.all()

            headers = ['订单编号', '顾客姓名', '手机号码', '收件地址', '创建时间',
                       '商品名称', '价格', '分类', '购买量', '状态']
            rows = []
            for o in orders:
                for item in o.items:
                    rows.append([
                        o.id, o.customer, o.phone, o.address, o.created_at,
                        item.product.name, item.product.price, item.product.category,
                        item.quantity, o.status
                    ])

        elif data_type == 'purchase':
            query = Purchase.query
            if start_date:
                query = query.filter(Purchase.created_at >= start_date)
            purchases = query.all()

            headers = ['货单编号', '货主姓名', '手机号码', '进货地址', '创建时间',
                       '商品名称', '价格', '分类', '进货量', '状态']
            rows = [[p.id, p.owner, p.phone, p.address, p.created_at,
                     p.product_name, p.product_price, p.product_category,
                     p.product_quantity, p.status] for p in purchases]

        else:
            flash('数据类型不合要求')
            return redirect(url_for('export'))

        # 生成 CSV 并返回
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)

        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = 'attachment; filename=data.csv'
        response.headers['Content-Type'] = 'text/csv'
        return response

    except Exception as e:
        print(e)
        flash('导出数据失败')

    return render_template('store/export.html')

@app.route('/store_logout')
def store_logout():
    session.pop('store_logged_in')
    return redirect(url_for('store_login'))

# --------------------------------------------------------------------

# ----------------------------顾客视图函数-------------------------------
@app.route('/customer_register' , methods=['GET','POST'])
def customer_register():
    if request.method == 'POST':
        try:
            username = request.form.get('username').strip()
            password = request.form.get('password')

            if not username or not password :
                flash('请输入账号和密码')
                return redirect(url_for('customer_register'))

            if Customer.query.filter_by(username=username).first():
                flash('该账号已存在')
                return redirect(url_for('customer_register'))

            new_customer = Customer(username=username)
            new_customer.set_password(password)
            db.session.add(new_customer)
            db.session.commit()
            flash('注册成功，请登录')
            return redirect(url_for('customer_login'))

        except Exception as e:
            db.session.rollback()
            print(e)
            flash('注册失败')
            return redirect(url_for('customer_register'))

    return render_template('customer/customer_register.html')

@app.route('/customer_login')
def customer_login():
    if request.method == 'POST':
        try:
            username = request.form.get('username').strip()
            password = request.form.get('password')

            if not username or not password :
                flash('请输入账号和密码')
                return redirect(url_for('customer_login'))

            customer = Customer.query.filter_by(username=username).first()
            if customer :
                if not customer.check_password(password):
                    flash('密码错误')
                    return redirect(url_for('customer_login'))

                session['username'] = username
                session['customer_logged_in'] = True
                flash('登录成功')
                return redirect(url_for('customer_dashboard'))

            flash('账号不存在，请先注册')
            return redirect(url_for('customer_register'))

        except Exception as e:
            print(e)
            flash('登录失败')

        return redirect(url_for('customer_login'))

    return render_template('customer/customer_login.html')

@app.route('/customer_dashboard')
def customer_dashboard():
    if not session.get('customer_logged_in'):
        flash('请先登录')
        return redirect(url_for('customer_login'))

    return render_template('customer/customer_dashboard.html')

@app.route('/customer/module/<name>')
def customer_module(name):
    if not session.get('customer_logged_in'):
        flash('请先登录')
        return redirect(url_for('customer_login'))
    allowed_modules = ['product_view','ordering','order_view']
    if name not in allowed_modules:
        abort(404)
    return redirect(url_for(name))

@app.route('/product_view', methods=['GET'])
def product_view():
    if not session.get('customer_logged_in'):
        flash('请先登录')
        return redirect(url_for('customer_login'))

    pagination = None
    products = []

    try:
        search = request.args.get('search', '', type=str)
        page = request.args.get('page', 1, type=int)
        per_page = 10

        query = Product.query
        if search:
            query = query.filter(Product.name.ilike(f'%{search}%'))

        pagination = query.order_by(Product.id).paginate(page=page, per_page=per_page, error_out=False)
        products = pagination.items

    except Exception as e:
        print(e)
        flash('查询失败')

    return render_template('customer/product_view.html',
                               products=products, pagination=pagination)

@app.route('/ordering', methods=['GET','POST'])
def ordering():
    if not session.get('customer_logged_in'):
        flash('请先登录')
        return redirect(url_for('customer_login'))
    if request.method == 'POST':
        try:
            customer = request.form.get('customer')
            phone = request.form.get('phone')
            address = request.form.get('address')
            product_id = int(request.form.get('product_id'))
            quantity = int(request.form.get('quantity'))
            product_choose = Product.query.get(product_id)

            if not customer or not phone or not address or quantity <= 0:
                flash('请填写完整的有效信息')
                return redirect(url_for('ordering'))

            if not product_choose :
                flash('该商品不存在')
                return redirect(url_for('ordering'))

            if product_choose.stock < quantity:
                flash('库存不足')
                return redirect(url_for('ordering'))

            # 创建订单
            new_order = Order(customer=customer, phone=phone, address=address)
            db.session.add(new_order)
            db.session.flush() # 获得new_order.id

            # 创建订单项
            new_order_item = OrderItem(order_id=new_order.id, product_id=product_id, quantity=quantity)
            db.session.add(new_order_item)
            product_choose.stock -= quantity

            db.session.commit()
            flash('订单已提交')
            return redirect(url_for('order_view'))

        except Exception as e:
            db.session.rollback()
            print(e)
            flash('提交订单失败')

    # GET渲染订单提交页面
    search = request.args.get('search', '', type=str)
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Product.query
    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))

    pagination = query.order_by(Product.id).paginate(page=page, per_page=per_page, error_out=False)
    products = pagination.items
    return render_template('customer/ordering.html',products=products,pagination=pagination)

@app.route('/order_view', methods=['GET'])
def order_view():
    if not session.get('customer_logged_in'):
        flash('请先登录')
        return redirect(url_for('customer_login'))

    pagination = None
    orders = []

    if request.method == 'GET':
        try:
            search = request.args.get('search', '', type=str)
            page = request.args.get('page', 1, type=int)
            per_page = 10

            query = Order.query
            if search:
                query = query.filter(Order.product_name.ilike(f'%{search}%'))

            pagination = query.order_by(Order.id).paginate(page=page, per_page=per_page, error_out=False)
            orders = pagination.items

        except Exception as e:
            print(e)
            flash('查询失败')

    return render_template('customer/order_view.html',
                               orders=orders, pagination=pagination)

@app.route('/customer_logout')
def customer_logout():
    session.pop('customer_logged_in')
    return redirect(url_for('customer_login'))

# ---------------------------------------------------------------------

# ----------------------------主程序运行---------------------------------
if __name__ == '__main__':
    port = os.environ.get('PORT', 5000)
    app.run(debug=True,port=port)
# ---------------------------------------------------------------------
