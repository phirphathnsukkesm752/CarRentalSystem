import hashlib
from abc import ABC, abstractmethod
from datetime import date, datetime
import random
import sys

import mysql.connector
from mysql.connector import Error
import pandas as pd
import streamlit as st


# ==========================================
# 0. HELPER FUNCTIONS
# ==========================================
def hash_password(password: str) -> str:
  """แปลง Password เป็น SHA-256 Hash เพื่อความปลอดภัย"""
  return hashlib.sha256(password.encode('utf-8')).hexdigest()


# ==========================================
# 1. DATABASE CONNECTION & AUTO INITIALIZER
# ==========================================
class DatabaseConnection:
  """Singleton Design Pattern สำหรับจัดการการเชื่อมต่อ MySQL"""

  _config = {
      'host': 'localhost',
      'user': 'root',
      'password': '',  # <--- ใส่รหัสผ่าน MySQL ของคุณที่นี่ (ถ้ามี)
      'database': 'car_rental_db',
      'port': 3306,
  }

  @classmethod
  def initialize_database(cls):
    """สร้าง Database, Tables และบัญชี Admin อัตโนมัติหากยังไม่มีในระบบ"""
    try:
      conn = mysql.connector.connect(
          host=cls._config['host'],
          user=cls._config['user'],
          password=cls._config['password'],
          port=cls._config['port'],
      )
      cursor = conn.cursor()
      cursor.execute(
          f"CREATE DATABASE IF NOT EXISTS `{cls._config['database']}` DEFAULT CHARACTER SET utf8mb4"
      )
      cursor.close()
      conn.close()

      conn = cls.get_connection()
      if not conn:
        return
      cursor = conn.cursor()

      # Table 1: users
      cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role ENUM('ADMIN', 'CUSTOMER') NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

      # Table 2: customers
      cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                name VARCHAR(100) NOT NULL,
                phone VARCHAR(20),
                email VARCHAR(100),
                address TEXT,
                driver_license VARCHAR(50),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

      # Table 3: vehicles
      cursor.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                brand VARCHAR(50) NOT NULL,
                model VARCHAR(50) NOT NULL,
                license_plate VARCHAR(20) UNIQUE NOT NULL,
                type VARCHAR(30),
                year INT,
                color VARCHAR(30),
                price_per_day DECIMAL(10,2) NOT NULL,
                status ENUM('AVAILABLE', 'RENTED', 'MAINTENANCE') DEFAULT 'AVAILABLE'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

      # Table 4: rentals
      cursor.execute("""
            CREATE TABLE IF NOT EXISTS rentals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                customer_id INT NOT NULL,
                vehicle_id INT NOT NULL,
                start_date DATE NOT NULL,
                due_date DATE NOT NULL,
                return_date DATE NULL,
                total_days INT NOT NULL,
                rental_price DECIMAL(10,2) NOT NULL,
                late_fee DECIMAL(10,2) DEFAULT 0.00,
                total_price DECIMAL(10,2) NOT NULL,
                status ENUM('ACTIVE', 'COMPLETED', 'CANCELLED') DEFAULT 'ACTIVE',
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

      # Table 5: payments
      cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                rental_id INT NOT NULL,
                payment_method VARCHAR(50) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) DEFAULT 'COMPLETED',
                FOREIGN KEY (rental_id) REFERENCES rentals(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

      # สร้าง default admin หากยังไม่มี
      cursor.execute(
          "SELECT COUNT(*) FROM users WHERE role = 'ADMIN' OR username = 'admin'"
      )
      if cursor.fetchone()[0] == 0:
        hashed_admin_pass = hash_password('admin123')
        cursor.execute(
            'INSERT INTO users (username, password, role) VALUES (%s, %s, %s)',
            ('admin', hashed_admin_pass, 'ADMIN'),
        )

      conn.commit()
      cursor.close()
      conn.close()

    except Error as e:
      print(f'Database initialization error: {e}')

  @classmethod
  def get_connection(cls):
    try:
      connection = mysql.connector.connect(**cls._config)
      return connection
    except Error as e:
      st.error(
          f'ไม่สามารถเชื่อมต่อฐานข้อมูล MySQL ได้ (Port 3306):\n{e}\n\nกรุณาตรวจสอบว่าเปิด'
          ' XAMPP / MySQL Service แล้วหรือยัง'
      )
      return None


def seed_100_vehicles():
  """ฟังก์ชันสร้างข้อมูลรถยนต์จำลอง 100 คันเข้าฐานข้อมูลอัตโนมัติหากยังไม่มีข้อมูล"""
  conn = DatabaseConnection.get_connection()
  if not conn:
    return

  cursor = conn.cursor()
  try:
    cursor.execute('SELECT COUNT(*) FROM vehicles')
    count = cursor.fetchone()[0]

    if count == 0:
      brands_models = [
          ('Toyota', ['Camry', 'Corolla Altis', 'Yaris Ativ', 'Fortuner', 'Cross']),
          ('Honda', ['Civic', 'City', 'Accord', 'CR-V', 'HR-V']),
          ('Nissan', ['Almera', 'Kicks', 'Navara', 'Terra', 'March']),
          ('Mazda', ['Mazda 2', 'Mazda 3', 'CX-30', 'CX-5', 'CX-3']),
          ('Isuzu', ['D-Max', 'Mu-X']),
          ('Ford', ['Ranger', 'Everest']),
          ('BYD', ['Atto 3', 'Dolphin', 'Seal']),
          ('MG', ['MG4', 'ZS', 'MG5']),
      ]
      types = ['Sedan', 'SUV', 'Hatchback', 'Pickup', 'EV']
      colors = ['ขาว', 'ดำ', 'เทา', 'บรอนซ์เงิน', 'แดง', 'น้ำเงิน']

      vehicles_data = []
      for i in range(1, 101):
        brand, models = random.choice(brands_models)
        model = random.choice(models)
        v_type = random.choice(types)
        color = random.choice(colors)
        year = random.randint(2019, 2024)
        price = float(
            random.choice([800, 1000, 1200, 1500, 1800, 2200, 2500, 3000])
        )
        license_plate = f"{random.choice(['กข', 'ขก', 'ชผ', 'ฮฮ', 'กก', '9ก'])} {random.randint(1000, 9999)}"

        vehicles_data.append((
            brand,
            model,
            license_plate,
            v_type,
            year,
            color,
            price,
            'AVAILABLE',
        ))

      query = """INSERT INTO vehicles (brand, model, license_plate, type, year, color, price_per_day, status)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
      cursor.executemany(query, vehicles_data)
      conn.commit()
  except Error as e:
    print(f'Seeding error: {e}')
  finally:
    cursor.close()
    conn.close()


# ==========================================
# 2. ENUMS & CONSTANTS
# ==========================================
class UserRole:
  ADMIN = 'ADMIN'
  CUSTOMER = 'CUSTOMER'


class VehicleStatus:
  AVAILABLE = 'AVAILABLE'
  RENTED = 'RENTED'
  MAINTENANCE = 'MAINTENANCE'


class RentalStatus:
  ACTIVE = 'ACTIVE'
  COMPLETED = 'COMPLETED'
  CANCELLED = 'CANCELLED'


STATUS_THAI = {
    'AVAILABLE': 'พร้อมใช้งาน',
    'RENTED': 'ถูกเช่าอยู่',
    'MAINTENANCE': 'ซ่อมบำรุง',
    'ACTIVE': 'กำลังเช่า',
    'COMPLETED': 'คืนรถแล้ว',
    'CANCELLED': 'ยกเลิกแล้ว',
}


# ==========================================
# 3. DOMAIN MODEL LAYER
# ==========================================
class User:

  def __init__(self, user_id=None, username='', password='', role=''):
    self._id = user_id
    self._username = username
    self._password = password
    self._role = role

  def get_id(self):
    return self._id

  def get_username(self):
    return self._username

  def get_role(self):
    return self._role


class Admin(User):

  def __init__(self, user_id=None, username='', password=''):
    super().__init__(user_id, username, password, UserRole.ADMIN)


class Customer(User):

  def __init__(
      self,
      user_id=None,
      username='',
      password='',
      customer_id=None,
      name='',
      phone='',
      email='',
      address='',
      driver_license='',
  ):
    super().__init__(user_id, username, password, UserRole.CUSTOMER)
    self._customer_id = customer_id
    self._name = name
    self._phone = phone
    self._email = email
    self._address = address
    self._driver_license = driver_license

  def get_customer_id(self):
    return self._customer_id

  def get_name(self):
    return self._name


class Vehicle:

  def __init__(
      self,
      vehicle_id=None,
      brand='',
      model='',
      license_plate='',
      vehicle_type='',
      year=2023,
      color='',
      price_per_day=0.0,
      status=VehicleStatus.AVAILABLE,
  ):
    self._id = vehicle_id
    self._brand = brand
    self._model = model
    self._license_plate = license_plate
    self._type = vehicle_type
    self._year = year
    self._color = color
    self._price_per_day = price_per_day
    self._status = status

  def get_id(self):
    return self._id

  def get_brand(self):
    return self._brand

  def get_model(self):
    return self._model

  def get_license_plate(self):
    return self._license_plate

  def get_type(self):
    return self._type

  def get_year(self):
    return self._year

  def get_color(self):
    return self._color

  def get_price_per_day(self):
    return self._price_per_day

  def get_status(self):
    return self._status


# ==========================================
# 4. POLYMORPHISM (PAYMENT SYSTEM)
# ==========================================
class PaymentMethod(ABC):

  @abstractmethod
  def process_payment(self, amount: float) -> bool:
    pass

  @abstractmethod
  def get_method_name(self) -> str:
    pass


class CashPayment(PaymentMethod):

  def process_payment(self, amount: float) -> bool:
    return True

  def get_method_name(self) -> str:
    return 'เงินสด (Cash)'


class CreditCardPayment(PaymentMethod):

  def __init__(self, card_number=''):
    self.card_number = card_number

  def process_payment(self, amount: float) -> bool:
    return True

  def get_method_name(self) -> str:
    return 'บัตรเครดิต (Credit Card)'


class BankTransferPayment(PaymentMethod):

  def __init__(self, ref_number=''):
    self.ref_number = ref_number

  def process_payment(self, amount: float) -> bool:
    return True

  def get_method_name(self) -> str:
    return 'โอนผ่านธนาคาร (Bank Transfer)'


# ==========================================
# 5. DATA ACCESS OBJECT (DAO LAYER)
# ==========================================
class UserDAO:

  def authenticate(self, username, password, expected_role):
    conn = DatabaseConnection.get_connection()
    if not conn:
      return None
    try:
      cursor = conn.cursor(dictionary=True)
      hashed_pwd = hash_password(password)

      query = (
          'SELECT * FROM users WHERE username = %s AND (password = %s OR'
          ' password = %s) AND role = %s'
      )
      cursor.execute(query, (username, hashed_pwd, password, expected_role))
      user_data = cursor.fetchone()
      cursor.close()

      if user_data:
        if user_data['role'] == UserRole.ADMIN:
          conn.close()
          return Admin(
              user_data['id'], user_data['username'], user_data['password']
          )
        else:
          c_cursor = conn.cursor(dictionary=True)
          c_cursor.execute(
              'SELECT * FROM customers WHERE user_id = %s', (user_data['id'],)
          )
          cust_data = c_cursor.fetchone()
          c_cursor.close()
          conn.close()
          if cust_data:
            return Customer(
                user_id=user_data['id'],
                username=user_data['username'],
                password=user_data['password'],
                customer_id=cust_data['id'],
                name=cust_data['name'],
                phone=cust_data['phone'],
                email=cust_data['email'],
                address=cust_data['address'],
                driver_license=cust_data['driver_license'],
            )
      conn.close()
    except Error as e:
      st.error(f'เกิดข้อผิดพลาดในการตรวจสอบข้อมูล: {e}')
    return None

  def register_customer(
      self, username, password, name, phone, email, address, license_num
  ):
    conn = DatabaseConnection.get_connection()
    if not conn:
      return False
    cursor = conn.cursor()
    try:
      hashed_pwd = hash_password(password)
      q1 = 'INSERT INTO users (username, password, role) VALUES (%s, %s, %s)'
      cursor.execute(q1, (username, hashed_pwd, UserRole.CUSTOMER))
      user_id = cursor.lastrowid

      q2 = """INSERT INTO customers (user_id, name, phone, email, address, driver_license) 
                    VALUES (%s, %s, %s, %s, %s, %s)"""
      cursor.execute(q2, (user_id, name, phone, email, address, license_num))
      conn.commit()
      return True
    except Error as e:
      conn.rollback()
      st.error(f'ข้อผิดพลาดการลงทะเบียน: {e}')
      return False
    finally:
      cursor.close()
      conn.close()


class VehicleDAO:

  def getAllVehicles(self):
    vehicles = []
    conn = DatabaseConnection.get_connection()
    if not conn:
      return vehicles
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM vehicles ORDER BY id ASC')
    rows = cursor.fetchall()
    for r in rows:
      v = Vehicle(
          r['id'],
          r['brand'],
          r['model'],
          r['license_plate'],
          r['type'],
          r['year'],
          r['color'],
          float(r['price_per_day']),
          r['status'],
      )
      vehicles.append(v)
    cursor.close()
    conn.close()
    return vehicles

  def addVehicle(self, vehicle: Vehicle):
    conn = DatabaseConnection.get_connection()
    if not conn:
      return False
    cursor = conn.cursor()
    query = """INSERT INTO vehicles (brand, model, license_plate, type, year, color, price_per_day, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
    try:
      cursor.execute(
          query,
          (
              vehicle.get_brand(),
              vehicle.get_model(),
              vehicle.get_license_plate(),
              vehicle.get_type(),
              vehicle.get_year(),
              vehicle.get_color(),
              vehicle.get_price_per_day(),
              vehicle.get_status(),
          ),
      )
      conn.commit()
      return True
    except Error as e:
      st.error(f'ข้อผิดพลาดฐานข้อมูล: {e}')
      return False
    finally:
      cursor.close()
      conn.close()

  def updateVehicle(self, vehicle: Vehicle):
    conn = DatabaseConnection.get_connection()
    if not conn:
      return False
    cursor = conn.cursor()
    query = """UPDATE vehicles 
                   SET brand=%s, model=%s, license_plate=%s, type=%s, year=%s, color=%s, price_per_day=%s, status=%s
                   WHERE id=%s"""
    try:
      cursor.execute(
          query,
          (
              vehicle.get_brand(),
              vehicle.get_model(),
              vehicle.get_license_plate(),
              vehicle.get_type(),
              vehicle.get_year(),
              vehicle.get_color(),
              vehicle.get_price_per_day(),
              vehicle.get_status(),
              vehicle.get_id(),
          ),
      )
      conn.commit()
      return True
    except Error as e:
      st.error(f'ข้อผิดพลาดการแก้ไข: {e}')
      return False
    finally:
      cursor.close()
      conn.close()

  def deleteVehicle(self, vehicle_id):
    conn = DatabaseConnection.get_connection()
    if not conn:
      return False
    cursor = conn.cursor()
    try:
      cursor.execute('DELETE FROM vehicles WHERE id = %s', (vehicle_id,))
      conn.commit()
      return True
    except Error as e:
      st.error('ไม่สามารถลบรถที่มีประวัติการเช่าค้างอยู่ได้')
      return False
    finally:
      cursor.close()
      conn.close()


class RentalDAO:

  def createRental(
      self,
      customer_id,
      vehicle_id,
      start_date,
      due_date,
      total_days,
      rental_price,
      total_price,
      payment_strategy: PaymentMethod,
  ):
    conn = DatabaseConnection.get_connection()
    if not conn:
      return False
    cursor = conn.cursor()
    try:
      q1 = """INSERT INTO rentals (customer_id, vehicle_id, start_date, due_date, total_days, rental_price, late_fee, total_price, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 0.0, %s, 'ACTIVE')"""
      cursor.execute(
          q1,
          (
              customer_id,
              vehicle_id,
              start_date,
              due_date,
              total_days,
              rental_price,
              total_price,
          ),
      )
      rental_id = cursor.lastrowid

      if payment_strategy.process_payment(total_price):
        q2 = """INSERT INTO payments (rental_id, payment_method, amount, status)
                VALUES (%s, %s, %s, 'COMPLETED')"""
        cursor.execute(
            q2, (rental_id, payment_strategy.get_method_name(), total_price)
        )

      q3 = "UPDATE vehicles SET status = 'RENTED' WHERE id = %s"
      cursor.execute(q3, (vehicle_id,))

      conn.commit()
      return True
    except Error as e:
      conn.rollback()
      st.error(f'ข้อผิดพลาดในการเช่า: {e}')
      return False
    finally:
      cursor.close()
      conn.close()

  def cancelRental(self, rental_id, vehicle_id):
    conn = DatabaseConnection.get_connection()
    if not conn:
      return False
    cursor = conn.cursor()
    try:
      q1 = "UPDATE rentals SET status = 'CANCELLED' WHERE id = %s"
      cursor.execute(q1, (rental_id,))

      q2 = "UPDATE vehicles SET status = 'AVAILABLE' WHERE id = %s"
      cursor.execute(q2, (vehicle_id,))

      conn.commit()
      return True
    except Error as e:
      conn.rollback()
      st.error(f'ข้อผิดพลาดการยกเลิก: {e}')
      return False
    finally:
      cursor.close()
      conn.close()

  def returnVehicle(
      self,
      rental_id,
      vehicle_id,
      actual_return_date,
      late_days,
      late_fee,
      extra_pay_method: PaymentMethod = None,
  ):
    conn = DatabaseConnection.get_connection()
    if not conn:
      return False
    cursor = conn.cursor()
    try:
      q1 = """UPDATE rentals 
                    SET return_date = %s, late_fee = %s, total_price = total_price + %s, status = 'COMPLETED'
                    WHERE id = %s"""
      cursor.execute(q1, (actual_return_date, late_fee, late_fee, rental_id))

      q2 = "UPDATE vehicles SET status = 'AVAILABLE' WHERE id = %s"
      cursor.execute(q2, (vehicle_id,))

      if late_fee > 0 and extra_pay_method:
        extra_pay_method.process_payment(late_fee)
        q3 = """INSERT INTO payments (rental_id, payment_method, amount, status)
                VALUES (%s, %s, %s, 'COMPLETED')"""
        cursor.execute(
            q3,
            (
                rental_id,
                f'ค่าปรับเกินเวลา ({extra_pay_method.get_method_name()})',
                late_fee,
            ),
        )

      conn.commit()
      return True
    except Error as e:
      conn.rollback()
      st.error(f'ข้อผิดพลาดการคืนรถ: {e}')
      return False
    finally:
      cursor.close()
      conn.close()

  def getRentalsByCustomer(self, customer_id):
    conn = DatabaseConnection.get_connection()
    if not conn:
      return []
    cursor = conn.cursor(dictionary=True)
    query = """SELECT r.*, v.brand, v.model, v.license_plate 
                   FROM rentals r 
                   JOIN vehicles v ON r.vehicle_id = v.id 
                   WHERE r.customer_id = %s ORDER BY r.id DESC"""
    cursor.execute(query, (customer_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

  def getAllRentals(self):
    conn = DatabaseConnection.get_connection()
    if not conn:
      return []
    cursor = conn.cursor(dictionary=True)
    query = """SELECT r.*, c.name as customer_name, v.brand, v.model, v.license_plate 
                   FROM rentals r 
                   JOIN customers c ON r.customer_id = c.id
                   JOIN vehicles v ON r.vehicle_id = v.id 
                   ORDER BY r.id DESC"""
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


# ==========================================
# 6. STREAMLIT WEB APP UI
# ==========================================
def main():
  st.set_page_config(
      page_title='Car Rental System', page_icon='🚗', layout='wide'
  )

  # Initial Setup Database
  DatabaseConnection.initialize_database()
  seed_100_vehicles()

  user_dao = UserDAO()
  vehicle_dao = VehicleDAO()
  rental_dao = RentalDAO()

  # Session State Management
  if 'user' not in st.session_state:
    st.session_state['user'] = None

  # ------------------------------------------
  # 6.1 LOGIN / REGISTER PAGES
  # ------------------------------------------
  if st.session_state['user'] is None:
    st.title('🚗 ระบบจัดการเช่ารถยนต์ (Car Rental Web App)')
    page_mode = st.sidebar.radio(
        'เลือกหน้าใช้งาน', ['เข้าสู่ระบบ', 'สมัครสมาชิกใหม่']
    )

    if page_mode == 'เข้าสู่ระบบ':
      st.subheader('🔑 เข้าสู่ระบบ')
      col1, col2 = st.columns([1, 2])

      with col1:
        role_choice = st.radio(
            'สิทธิ์การใช้งาน', ['ลูกค้า (Customer)', 'ผู้ดูแลระบบ (Admin)']
        )
        selected_role = (
            UserRole.ADMIN
            if 'Admin' in role_choice
            else UserRole.CUSTOMER
        )

        username = st.text_input('ชื่อผู้ใช้งาน (Username)')
        password = st.text_input('รหัสผ่าน (Password)', type='password')

        if st.button('เข้าสู่ระบบ', type='primary', use_container_width=True):
          user = user_dao.authenticate(
              username.strip(), password.strip(), selected_role
          )
          if user:
            st.session_state['user'] = user
            st.success('เข้าสู่ระบบสำเร็จ!')
            st.rerun()
          else:
            st.error('ชื่อผู้ใช้ รหัสผ่าน หรือสิทธิ์การใช้งานไม่ถูกต้อง')

    elif page_mode == 'สมัครสมาชิกใหม่':
      st.subheader('📝 สมัครสมาชิกใหม่ (สำหรับลูกค้า)')
      with st.form('reg_form'):
        reg_user = st.text_input('Username*')
        reg_pass = st.text_input('Password*', type='password')
        reg_name = st.text_input('ชื่อ-นามสกุล*')
        reg_phone = st.text_input('เบอร์โทรศัพท์*')
        reg_email = st.text_input('อีเมล*')
        reg_address = st.text_area('ที่อยู่*')
        reg_license = st.text_input('เลขที่ใบขับขี่*')

        submit_reg = st.form_submit_button(
            'ยืนยันการลงทะเบียน', type='primary'
        )

        if submit_reg:
          if not (
              reg_user
              and reg_pass
              and reg_name
              and reg_phone
              and reg_email
              and reg_address
              and reg_license
          ):
            st.warning('กรุณากรอกข้อมูลให้ครบถ้วนทุกช่อง')
          else:
            success = user_dao.register_customer(
                reg_user.strip(),
                reg_pass.strip(),
                reg_name.strip(),
                reg_phone.strip(),
                reg_email.strip(),
                reg_address.strip(),
                reg_license.strip(),
            )
            if success:
              st.success(
                  'ลงทะเบียนเรียบร้อยแล้ว! กรุณาเปลี่ยนเป็นหน้า "เข้าสู่ระบบ"'
              )

  # ------------------------------------------
  # 6.2 MAIN DASHBOARD (LOGGED IN)
  # ------------------------------------------
  else:
    current_user = st.session_state['user']

    # Sidebar Logout & User Info
    st.sidebar.markdown(
        f'### 👤 สวัสดี: **{current_user.get_username()}**'
    )
    st.sidebar.caption(f'สิทธิ์การใช้งาน: {current_user.get_role()}')
    if st.sidebar.button('🚪 ออกจากระบบ', type='secondary'):
      st.session_state['user'] = None
      st.rerun()

    # ==========================================
    # ADMIN VIEW
    # ==========================================
    if current_user.get_role() == UserRole.ADMIN:
      st.title(
          f'👑 แผงควบคุมผู้ดูแลระบบ (Admin: {current_user.get_username()})'
      )

      tab1, tab2 = st.tabs(
          ['🚗 จัดการข้อมูลรถยนต์', '📋 รายการเช่าและรับคืนรถ']
      )

      # TAB 1: จัดการข้อมูลรถยนต์
      with tab1:
        st.subheader('รายการรถยนต์ทั้งหมดในระบบ')

        vehicles_list = vehicle_dao.getAllVehicles()
        v_data = []
        for v in vehicles_list:
          v_data.append({
              'รหัส': v.get_id(),
              'ยี่ห้อ': v.get_brand(),
              'รุ่น': v.get_model(),
              'ทะเบียน': v.get_license_plate(),
              'ประเภท': v.get_type(),
              'ปี': v.get_year(),
              'สี': v.get_color(),
              'ราคา/วัน': f'฿{v.get_price_per_day():,.2f}',
              'สถานะ': STATUS_THAI.get(v.get_status(), v.get_status()),
          })
        df_v = pd.DataFrame(v_data)
        st.dataframe(df_v, use_container_width=True, height=350)

        st.divider()

        # Action: เพิ่ม / แก้ไข / ลบ รถยนต์
        col_add, col_edit, col_del = st.columns(3)

        with col_add:
          with st.expander('➕ เพิ่มรถยนต์ใหม่'):
            with st.form('add_v_form'):
              b = st.text_input('ยี่ห้อ')
              m = st.text_input('รุ่น')
              l = st.text_input('ทะเบียนรถ')
              t = st.text_input('ประเภทรถ')
              y = st.number_input('ปีรถ (ค.ศ.)', value=2023, step=1)
              c = st.text_input('สีรถ')
              p = st.number_input('ราคาเช่าต่อวัน', value=1000.0, step=100.0)

              if st.form_submit_button('บันทึกรถยนต์'):
                if b and m and l:
                  new_v = Vehicle(
                      brand=b,
                      model=m,
                      license_plate=l,
                      vehicle_type=t,
                      year=int(y),
                      color=c,
                      price_per_day=float(p),
                  )
                  if vehicle_dao.addVehicle(new_v):
                    st.success('เพิ่มรถยนต์สำเร็จ!')
                    st.rerun()

        with col_edit:
          with st.expander('✏️ แก้ไขข้อมูลรถยนต์'):
            v_id_to_edit = st.number_input(
                'ระบุรหัสรถยนต์ที่ต้องการแก้ไข', min_value=1, step=1
            )
            v_obj = next(
                (x for x in vehicles_list if x.get_id() == v_id_to_edit), None
            )

            if v_obj:
              eb = st.text_input('ยี่ห้อ', value=v_obj.get_brand())
              em = st.text_input('รุ่น', value=v_obj.get_model())
              el = st.text_input('ทะเบียนรถ', value=v_obj.get_license_plate())
              et = st.text_input('ประเภท', value=v_obj.get_type())
              ey = st.number_input(
                  'ปีรถ', value=int(v_obj.get_year()), step=1
              )
              ec = st.text_input('สี', value=v_obj.get_color())
              ep = st.number_input(
                  'ราคา/วัน',
                  value=float(v_obj.get_price_per_day()),
                  step=100.0,
              )
              es = st.selectbox(
                  'สถานะ',
                  ['พร้อมใช้งาน', 'ถูกเช่าอยู่', 'ซ่อมบำรุง'],
                  index=[
                      'AVAILABLE',
                      'RENTED',
                      'MAINTENANCE',
                  ].index(v_obj.get_status()),
              )

              rev_status = {
                  'พร้อมใช้งาน': 'AVAILABLE',
                  'ถูกเช่าอยู่': 'RENTED',
                  'ซ่อมบำรุง': 'MAINTENANCE',
              }

              if st.button('อัปเดตข้อมูลรถ'):
                updated_v = Vehicle(
                    vehicle_id=v_id_to_edit,
                    brand=eb,
                    model=em,
                    license_plate=el,
                    vehicle_type=et,
                    year=int(ey),
                    color=ec,
                    price_per_day=float(ep),
                    status=rev_status[es],
                )
                if vehicle_dao.updateVehicle(updated_v):
                  st.success('อัปเดตข้อมูลสำเร็จ!')
                  st.rerun()

        with col_del:
          with st.expander('🗑️ ลบรถยนต์'):
            v_id_to_del = st.number_input(
                'ระบุรหัสรถยนต์ที่ต้องการลบ', min_value=1, step=1
            )
            if st.button('ยืนยันการลบรถยนต์', type='primary'):
              if vehicle_dao.deleteVehicle(v_id_to_del):
                st.success('ลบรถยนต์เรียบร้อย!')
                st.rerun()

      # TAB 2: รายการเช่าและรับคืนรถ
      with tab2:
        st.subheader('รายการประวัติการเช่าทั้งหมด')
        rentals_all = rental_dao.getAllRentals()

        r_data = []
        for r in rentals_all:
          r_data.append({
              'รหัสเช่า': r['id'],
              'ชื่อลูกค้า': r['customer_name'],
              'รุ่นรถ': f"{r['brand']} {r['model']}",
              'ทะเบียน': r['license_plate'],
              'เริ่มเช่า': r['start_date'],
              'กำหนดคืน': r['due_date'],
              'คืนจริง': r['return_date'] or '-',
              'ราคารวม': f"฿{r['total_price']:,.2f}",
              'สถานะ': STATUS_THAI.get(r['status'], r['status']),
          })
        st.dataframe(pd.DataFrame(r_data), use_container_width=True, height=300)

        st.divider()

        col_ret, col_can = st.columns(2)

        with col_ret:
          st.markdown('#### 📥 บันทึกรับคืนรถยนต์ (Return Vehicle)')
          ret_r_id = st.number_input(
              'ระบุรหัสเช่าที่ต้องการรับคืน', min_value=1, step=1
          )

          if st.button('คำนวณและทำรายการรับคืน'):
            r_target = next(
                (x for x in rentals_all if x['id'] == ret_r_id), None
            )
            if not r_target:
              st.error('ไม่พบรหัสเช่านี้')
            elif r_target['status'] != 'ACTIVE':
              st.warning(
                  'รายการนี้ไม่ได้อยู่ในสถานะ "กำลังเช่า" ไม่สามารถคืนรถได้'
              )
            else:
              today = date.today()
              due_d = r_target['due_date']
              late_days = (today - due_d).days if today > due_d else 0
              late_fee = late_days * 500.0

              pay_strat = CashPayment()
              if late_fee > 0:
                st.warning(
                    f'เกินกำหนด {late_days} วัน! มีค่าปรับเพิ่มเติม:'
                    f' ฿{late_fee:,.2f}'
                )

              if rental_dao.returnVehicle(
                  ret_r_id,
                  r_target['vehicle_id'],
                  today,
                  late_days,
                  late_fee,
                  pay_strat,
              ):
                st.success(
                    'บันทึกการคืนรถสำเร็จ!'
                    f' ค่าปรับเพิ่มเติม: ฿{late_fee:,.2f}'
                )
                st.rerun()

        with col_can:
          st.markdown('#### ❌ ยกเลิกการเช่า (Cancel)')
          can_r_id = st.number_input(
              'ระบุรหัสเช่าที่ต้องการยกเลิก', min_value=1, step=1
          )
          if st.button('ยกเลิกรายการเช่านี้'):
            r_target = next(
                (x for x in rentals_all if x['id'] == can_r_id), None
            )
            if r_target and r_target['status'] == 'ACTIVE':
              if rental_dao.cancelRental(can_r_id, r_target['vehicle_id']):
                st.success('ยกเลิกการเช่าสำเร็จ!')
                st.rerun()
            else:
              st.error('ไม่สามารถยกเลิกรายการนี้ได้')

    # ==========================================
    # CUSTOMER VIEW
    # ==========================================
    else:
      cust: Customer = current_user
      st.title(f'👤 บริการเช่ารถยนต์ (คุณ{cust.get_name()})')

      tab1, tab2 = st.tabs(
          ['🚘 เลือกรถและทำรายการเช่า', '📜 ประวัติการเช่าของฉัน']
      )

      # TAB 1: เลือกรถและทำรายการเช่า
      with tab1:
        st.subheader('ค้นหาและเลือกรถยนต์ที่ต้องการเช่า')

        kw = st.text_input('🔍 ค้นหารถ (พิมพ์ ยี่ห้อ / รุ่น / ประเภท)')

        all_v = vehicle_dao.getAllVehicles()
        filtered_v = []
        for v in all_v:
          full_str = (
              f'{v.get_brand()} {v.get_model()} {v.get_type()}'.lower()
          )
          if not kw or kw.lower() in full_str:
            filtered_v.append({
                'รหัส': v.get_id(),
                'ยี่ห้อ': v.get_brand(),
                'รุ่น': v.get_model(),
                'ทะเบียน': v.get_license_plate(),
                'ประเภท': v.get_type(),
                'ปี': v.get_year(),
                'สี': v.get_color(),
                'ราคา/วัน (บาท)': v.get_price_per_day(),
                'สถานะ': STATUS_THAI.get(v.get_status(), v.get_status()),
            })

        df_avail = pd.DataFrame(filtered_v)
        st.dataframe(df_avail, use_container_width=True, height=350)

        st.divider()

        st.markdown('#### 🔑 ทำรายการเช่ารถยนต์')
        col_rent1, col_rent2, col_rent3 = st.columns(3)

        with col_rent1:
          selected_v_id = st.number_input(
              'ระบุรหัสรถยนต์ที่ต้องการเช่า', min_value=1, step=1
          )
        with col_rent2:
          rent_days = st.number_input(
              'จำนวนวันที่ต้องการเช่า (วัน)', min_value=1, value=1, step=1
          )
        with col_rent3:
          pay_method_type = st.selectbox(
              'ช่องทางชำระเงิน',
              [
                  '💵 เงินสด (Cash)',
                  '💳 บัตรเครดิต (Credit Card)',
                  '🏦 โอนผ่านธนาคาร (Bank Transfer)',
              ],
          )

        # คำนวณยอดเงิน
        target_v = next(
            (x for x in all_v if x.get_id() == selected_v_id), None
        )
        if target_v:
          total_price = rent_days * target_v.get_price_per_day()
          st.info(
              f'ยี่ห้อ/รุ่น: **{target_v.get_brand()} {target_v.get_model()}**'
              f' | ยอดชำระทั้งหมด: **฿{total_price:,.2f}**'
          )

          if st.button(
              '🔑 ยืนยันชำระเงินและทำรายการเช่า', type='primary'
          ):
            if target_v.get_status() != 'AVAILABLE':
              st.error(
                  'รถยนต์คันนี้ไม่พร้อมใช้งานสำหรับการเช่า (ถูกเช่าหรือซ่อมบำรุงอยู่)'
              )
            else:
              payment_strategy = CashPayment()
              if 'บัตรเครดิต' in pay_method_type:
                payment_strategy = CreditCardPayment('4111-2222-3333-4444')
              elif 'โอนผ่านธนาคาร' in pay_method_type:
                payment_strategy = BankTransferPayment('TXN-ONLINE-999')

              start_d = date.today()
              due_d = date.fromordinal(start_d.toordinal() + int(rent_days))

              if rental_dao.createRental(
                  cust.get_customer_id(),
                  target_v.get_id(),
                  start_d,
                  due_d,
                  int(rent_days),
                  target_v.get_price_per_day(),
                  total_price,
                  payment_strategy,
              ):
                st.success(
                    'ทำรายการเช่าสำเร็จ!'
                    f' กำหนดคืนวันที่: {due_d.strftime("%d/%m/%Y")}'
                )
                st.rerun()

      # TAB 2: ประวัติการเช่าของฉัน
      with tab2:
        st.subheader('ประวัติการเช่าของฉัน')
        my_rentals = rental_dao.getRentalsByCustomer(cust.get_customer_id())

        my_r_data = []
        for r in my_rentals:
          my_r_data.append({
              'รหัสเช่า': r['id'],
              'รถยนต์ที่เช่า': f"{r['brand']} {r['model']}",
              'ทะเบียน': r['license_plate'],
              'เริ่มเช่า': r['start_date'],
              'กำหนดคืน': r['due_date'],
              'คืนจริง': r['return_date'] or '-',
              'ราคารวม': f"฿{r['total_price']:,.2f}",
              'สถานะ': STATUS_THAI.get(r['status'], r['status']),
          })

        st.dataframe(
            pd.DataFrame(my_r_data), use_container_width=True, height=300
        )

        st.divider()

        # ยกเลิกรายการ
        st.markdown('#### ❌ ยกเลิกรายการเช่า')
        cancel_id = st.number_input(
            'ระบุรหัสเช่าที่ต้องการยกเลิก', min_value=1, step=1
        )
        if st.button('ยกเลิกรายการเช่านี้'):
          r_target = next((x for x in my_rentals if x['id'] == cancel_id), None)
          if r_target and r_target['status'] == 'ACTIVE':
            if rental_dao.cancelRental(cancel_id, r_target['vehicle_id']):
              st.success('ยกเลิกรายการเช่าเรียบร้อยแล้ว!')
              st.rerun()
          else:
            st.error(
                'ไม่พบรายการ หรือรายการไม่อยู่ในสถานะ "กำลังเช่า"'
                ' ไม่สามารถยกเลิกได้'
            )


if __name__ == '__main__':
  main()