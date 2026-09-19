import hashlib
from abc import ABC, abstractmethod
from datetime import date, datetime
import random
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import mysql.connector
from mysql.connector import Error


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
      # เชื่อมต่อแบบยังไม่ระบุฐานข้อมูลเพื่อสร้าง Database
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

      # เชื่อมต่อฐานข้อมูล car_rental_db เพื่อสร้าง Tables
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
      messagebox.showerror(
          'ข้อผิดพลาดฐานข้อมูล',
          f'ไม่สามารถเชื่อมต่อฐานข้อมูล MySQL ได้ (Port 3306):\n{e}\n\n'
          'กรุณาตรวจสอบว่าเปิด XAMPP / MySQL Service แล้วหรือยัง',
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
        price = float(random.choice([800, 1000, 1200, 1500, 1800, 2200, 2500, 3000]))
        license_plate = f"{random.choice(['กข', 'ขก', 'ชผ', 'ฮฮ', 'กก', '9ก'])} {random.randint(1000, 9999)}"

        vehicles_data.append(
            (brand, model, license_plate, v_type, year, color, price, 'AVAILABLE')
        )

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

      # ตรวจสอบรหัสผ่านทั้งแบบ Hash และ Plain (รวมถึงตรวจสอบ Role ที่เลือก)
      query = 'SELECT * FROM users WHERE username = %s AND (password = %s OR password = %s) AND role = %s'
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
      messagebox.showerror(
          'ข้อผิดพลาด', f'เกิดข้อผิดพลาดในการตรวจสอบข้อมูล: {e}'
      )
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
      messagebox.showerror('ข้อผิดพลาดการลงทะเบียน', str(e))
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
      messagebox.showerror('ข้อผิดพลาดฐานข้อมูล', str(e))
      return False
    finally:
      cursor.close()
      conn.close()

  def updateVehicle(self, vehicle: Vehicle):
    """แก้ไขข้อมูลรถยนต์"""
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
      messagebox.showerror('ข้อผิดพลาดการแก้ไข', str(e))
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
      messagebox.showerror(
          'ข้อผิดพลาด', 'ไม่สามารถลบรถที่มีประวัติการเช่าค้างอยู่ได้'
      )
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
      messagebox.showerror('ข้อผิดพลาดในการเช่า', str(e))
      return False
    finally:
      cursor.close()
      conn.close()

  def cancelRental(self, rental_id, vehicle_id):
    """ยกเลิกการเช่ารถยนต์และคืนสถานะรถยนต์"""
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
      messagebox.showerror('ข้อผิดพลาดการยกเลิก', str(e))
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
      messagebox.showerror('ข้อผิดพลาดการคืนรถ', str(e))
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
# 6. GUI LAYER (MODERN THAI INTERFACE)
# ==========================================
class MainApplication(tk.Tk):

  def __init__(self):
    super().__init__()
    self.title('ระบบจัดการเช่ารถยนต์ (Car Rental System - OOP & MySQL)')
    self.geometry('1100x720')
    self.configure(bg='#F4F6F9')

    # สร้าง DB, Tables และรถยนต์จำลอง 100 คัน อัตโนมัติ
    DatabaseConnection.initialize_database()
    seed_100_vehicles()

    self.setup_styles()

    self.user_dao = UserDAO()
    self.vehicle_dao = VehicleDAO()
    self.rental_dao = RentalDAO()

    self.current_user = None
    self.show_login_frame()

  def setup_styles(self):
    self.style = ttk.Style()
    self.style.theme_use('clam')

    PRIMARY_COLOR = '#1E3A8A'
    SECONDARY_COLOR = '#0D9488'
    BG_COLOR = '#F4F6F9'
    TEXT_COLOR = '#1F2937'
    WHITE = '#FFFFFF'

    self.style.configure('.', background=BG_COLOR, foreground=TEXT_COLOR)
    self.style.configure('TFrame', background=BG_COLOR)
    self.style.configure('Card.TFrame', background=WHITE, relief='flat')
    self.style.configure('White.TFrame', background=WHITE)

    self.style.configure(
        'TLabel', background=BG_COLOR, font=('Tahoma', 10), foreground=TEXT_COLOR
    )
    self.style.configure(
        'White.TLabel',
        background=WHITE,
        font=('Tahoma', 10),
        foreground=TEXT_COLOR,
    )
    self.style.configure(
        'Header.TLabel',
        font=('Tahoma', 18, 'bold'),
        foreground=PRIMARY_COLOR,
        background=BG_COLOR,
    )
    self.style.configure(
        'WhiteHeader.TLabel',
        font=('Tahoma', 18, 'bold'),
        foreground=PRIMARY_COLOR,
        background=WHITE,
    )

    self.style.configure('TRadiobutton', background=WHITE)
    self.style.configure('TEntry', fieldbackground=WHITE, font=('Tahoma', 10))

    self.style.configure(
        'Primary.TButton',
        font=('Tahoma', 10, 'bold'),
        background=PRIMARY_COLOR,
        foreground=WHITE,
        borderwidth=0,
    )
    self.style.map(
        'Primary.TButton',
        background=[('active', '#1D4ED8'), ('disabled', '#9CA3AF')],
    )

    self.style.configure(
        'Success.TButton',
        font=('Tahoma', 10, 'bold'),
        background=SECONDARY_COLOR,
        foreground=WHITE,
        borderwidth=0,
    )
    self.style.map('Success.TButton', background=[('active', '#14B8A6')])

    self.style.configure(
        'Danger.TButton',
        font=('Tahoma', 10, 'bold'),
        background='#DC2626',
        foreground=WHITE,
        borderwidth=0,
    )
    self.style.map('Danger.TButton', background=[('active', '#EF4444')])

    self.style.configure(
        'TNotebook', background=BG_COLOR, tabmargins=[2, 5, 2, 0]
    )
    self.style.configure(
        'TNotebook.Tab',
        font=('Tahoma', 10, 'bold'),
        padding=[15, 8],
        background='#E5E7EB',
        foreground=TEXT_COLOR,
    )
    self.style.map(
        'TNotebook.Tab',
        background=[('selected', PRIMARY_COLOR)],
        foreground=[('selected', WHITE)],
    )

    self.style.configure(
        'Treeview',
        font=('Tahoma', 9),
        rowheight=28,
        background=WHITE,
        fieldbackground=WHITE,
        bordercolor='#E5E7EB',
    )
    self.style.configure(
        'Treeview.Heading',
        font=('Tahoma', 10, 'bold'),
        background=PRIMARY_COLOR,
        foreground=WHITE,
        relief='flat',
    )
    self.style.map(
        'Treeview',
        background=[('selected', '#3B82F6')],
        foreground=[('selected', WHITE)],
    )

  def clear_screen(self):
    for widget in self.winfo_children():
      widget.destroy()

  # --- LOGIN & REGISTER VIEWS ---
  def show_login_frame(self):
    self.clear_screen()

    card = ttk.Frame(self, style='Card.TFrame', padding=35)
    card.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    ttk.Label(
        card, text='🚗 เข้าสู่ระบบเช่ารถยนต์', style='WhiteHeader.TLabel'
    ).grid(row=0, column=0, columnspan=2, pady=(0, 20))

    ttk.Label(card, text='สิทธิ์การใช้งาน:', style='White.TLabel').grid(
        row=1, column=0, sticky=tk.W, pady=8
    )
    role_var = tk.StringVar(value=UserRole.CUSTOMER)
    role_frame = ttk.Frame(card, style='White.TFrame')
    role_frame.grid(row=1, column=1, sticky=tk.W, pady=8, padx=(10, 0))

    ttk.Radiobutton(
        role_frame,
        text='ลูกค้า (Customer)',
        value=UserRole.CUSTOMER,
        variable=role_var,
        style='TRadiobutton',
    ).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Radiobutton(
        role_frame,
        text='ผู้ดูแลระบบ (Admin)',
        value=UserRole.ADMIN,
        variable=role_var,
        style='TRadiobutton',
    ).pack(side=tk.LEFT)

    ttk.Label(
        card, text='ชื่อผู้ใช้งาน (Username):', style='White.TLabel'
    ).grid(row=2, column=0, sticky=tk.W, pady=8)
    entry_user = ttk.Entry(card, width=28)
    entry_user.grid(row=2, column=1, pady=8, padx=(10, 0))

    ttk.Label(card, text='รหัสผ่าน (Password):', style='White.TLabel').grid(
        row=3, column=0, sticky=tk.W, pady=8
    )
    entry_pass = ttk.Entry(card, show='*', width=28)
    entry_pass.grid(row=3, column=1, pady=8, padx=(10, 0))

    def do_login():
      selected_role = role_var.get()
      user = self.user_dao.authenticate(
          entry_user.get().strip(), entry_pass.get().strip(), selected_role
      )
      if user:
        self.current_user = user
        if user.get_role() == UserRole.ADMIN:
          self.show_admin_dashboard()
        else:
          self.show_customer_dashboard()
      else:
        messagebox.showerror(
            'เข้าสู่ระบบไม่สำเร็จ',
            'ชื่อผู้ใช้ รหัสผ่าน หรือสิทธิ์การใช้งานไม่ถูกต้อง',
        )

    btn_login = ttk.Button(
        card, text='เข้าสู่ระบบ', style='Primary.TButton', command=do_login
    )
    btn_login.grid(row=4, column=0, columnspan=2, pady=(20, 10), sticky=tk.EW)

    btn_reg = ttk.Button(
        card,
        text='ลงทะเบียนผู้ใช้งานใหม่ (เฉพาะลูกค้า)',
        style='Success.TButton',
        command=self.show_register_frame,
    )
    btn_reg.grid(row=5, column=0, columnspan=2, sticky=tk.EW)

  def show_register_frame(self):
    self.clear_screen()

    card = ttk.Frame(self, style='Card.TFrame', padding=30)
    card.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    ttk.Label(
        card, text='📝 สมัครสมาชิกใหม่ (ลูกค้า)', style='WhiteHeader.TLabel'
    ).grid(row=0, column=0, columnspan=2, pady=(0, 15))

    fields = [
        ('Username', 'ชื่อผู้ใช้:'),
        ('Password', 'รหัสผ่าน:'),
        ('Full Name', 'ชื่อ-นามสกุล:'),
        ('Phone', 'เบอร์โทรศัพท์:'),
        ('Email', 'อีเมล:'),
        ('Address', 'ที่อยู่:'),
        ('Driver License', 'ใบขับขี่:'),
    ]
    entries = {}

    for idx, (key, label_text) in enumerate(fields, start=1):
      ttk.Label(card, text=label_text, style='White.TLabel').grid(
          row=idx, column=0, sticky=tk.W, pady=5
      )
      ent = ttk.Entry(card, width=32, show='*' if key == 'Password' else '')
      ent.grid(row=idx, column=1, pady=5, padx=(10, 0))
      entries[key] = ent

    def do_register():
      if not all(entries[k].get().strip() for k in entries):
        messagebox.showwarning('แจ้งเตือน', 'กรุณากรอกข้อมูลให้ครบถ้วนทุกช่อง')
        return

      success = self.user_dao.register_customer(
          entries['Username'].get().strip(),
          entries['Password'].get().strip(),
          entries['Full Name'].get().strip(),
          entries['Phone'].get().strip(),
          entries['Email'].get().strip(),
          entries['Address'].get().strip(),
          entries['Driver License'].get().strip(),
      )
      if success:
        messagebox.showinfo(
            'สำเร็จ', 'ลงทะเบียนเรียบร้อยแล้ว! กรุณาเข้าสู่ระบบ'
        )
        self.show_login_frame()

    ttk.Button(
        card,
        text='ยืนยันการลงทะเบียน',
        style='Success.TButton',
        command=do_register,
    ).grid(row=len(fields) + 1, column=0, columnspan=2, pady=(15, 5), sticky=tk.EW)

    ttk.Button(
        card,
        text='กลับสู่หน้าเข้าสู่ระบบ',
        style='Primary.TButton',
        command=self.show_login_frame,
    ).grid(row=len(fields) + 2, column=0, columnspan=2, sticky=tk.EW)

  # --- ADMIN DASHBOARD ---
  def show_admin_dashboard(self):
    self.clear_screen()

    header = ttk.Frame(self, padding=(15, 10))
    header.pack(fill=tk.X)
    ttk.Label(
        header,
        text=(
            '👑 แผงควบคุมผู้ดูแลระบบ (ผู้ใช้:'
            f' {self.current_user.get_username()})'
        ),
        style='Header.TLabel',
    ).pack(side=tk.LEFT)
    ttk.Button(
        header,
        text='ออกจากระบบ',
        style='Danger.TButton',
        command=self.show_login_frame,
    ).pack(side=tk.RIGHT)

    notebook = ttk.Notebook(self)
    notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

    tab_vehicles = ttk.Frame(notebook, padding=10)
    tab_rentals = ttk.Frame(notebook, padding=10)

    notebook.add(tab_vehicles, text=' 🚗 จัดการข้อมูลรถยนต์ ')
    notebook.add(tab_rentals, text=' 📋 รายการเช่าและรับคืนรถ ')

    self.setup_admin_vehicles_tab(tab_vehicles)
    self.setup_admin_rentals_tab(tab_rentals)

  def setup_admin_vehicles_tab(self, parent):
    top_btn_frame = ttk.Frame(parent)
    top_btn_frame.pack(fill=tk.X, pady=(0, 10))

    columns = (
        'id',
        'brand',
        'model',
        'license',
        'type',
        'year',
        'color',
        'price',
        'status',
    )
    headers = (
        'รหัส',
        'ยี่ห้อ',
        'รุ่น',
        'ทะเบียน',
        'ประเภท',
        'ปี',
        'สี',
        'ราคา/วัน',
        'สถานะ',
    )

    tree = ttk.Treeview(parent, columns=columns, show='headings')
    for c, h in zip(columns, headers):
      tree.heading(c, text=h)
      tree.column(c, width=100, anchor=tk.CENTER)

    scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscroll=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    tree.pack(fill=tk.BOTH, expand=True)

    def load_vehicles():
      for i in tree.get_children():
        tree.delete(i)
      for v in self.vehicle_dao.getAllVehicles():
        status_th = STATUS_THAI.get(v.get_status(), v.get_status())
        tree.insert(
            '',
            tk.END,
            values=(
                v.get_id(),
                v.get_brand(),
                v.get_model(),
                v.get_license_plate(),
                v.get_type(),
                v.get_year(),
                v.get_color(),
                f'฿{v.get_price_per_day():,.2f}',
                status_th,
            ),
        )

    def add_vehicle_dialog():
      dlg = tk.Toplevel(self)
      dlg.title('เพิ่มข้อมูลรถยนต์ใหม่')
      dlg.geometry('350x450')
      dlg.configure(bg='#FFFFFF')

      fields = [
          ('Brand', 'ยี่ห้อ:'),
          ('Model', 'รุ่น:'),
          ('License Plate', 'ทะเบียนรถ:'),
          ('Type', 'ประเภทรถ:'),
          ('Year', 'ปีรถ (ค.ศ.):'),
          ('Color', 'สีรถ:'),
          ('Price Per Day', 'ราคาเช่าต่อวัน:'),
      ]
      entries = {}
      for idx, (k, label_text) in enumerate(fields):
        ttk.Label(dlg, text=label_text, style='White.TLabel').pack(
            anchor=tk.W, padx=25, pady=(5, 0)
        )
        e = ttk.Entry(dlg, width=30)
        e.pack(padx=25, pady=(0, 5))
        entries[k] = e

      def save():
        try:
          v = Vehicle(
              brand=entries['Brand'].get(),
              model=entries['Model'].get(),
              license_plate=entries['License Plate'].get(),
              vehicle_type=entries['Type'].get(),
              year=int(entries['Year'].get()),
              color=entries['Color'].get(),
              price_per_day=float(entries['Price Per Day'].get()),
          )
          if self.vehicle_dao.addVehicle(v):
            messagebox.showinfo('สำเร็จ', 'บันทึกข้อมูลรถยนต์เรียบร้อย')
            dlg.destroy()
            load_vehicles()
        except Exception:
          messagebox.showerror(
              'ข้อมูลไม่ถูกต้อง', 'กรุณาตรวจสอบตัวเลขในช่อง ปี และ ราคาเช่า'
          )

      ttk.Button(
          dlg, text='บันทึกข้อมูล', style='Success.TButton', command=save
      ).pack(pady=15, fill=tk.X, padx=25)

    def edit_vehicle_dialog():
      selected = tree.selection()
      if not selected:
        messagebox.showwarning('แจ้งเตือน', 'กรุณาเลือกรถยนต์ที่ต้องการแก้ไข')
        return

      item_vals = tree.item(selected[0])['values']
      v_id = item_vals[0]

      dlg = tk.Toplevel(self)
      dlg.title(f'แก้ไขข้อมูลรถยนต์ (รหัส: {v_id})')
      dlg.geometry('350x520')
      dlg.configure(bg='#FFFFFF')

      fields = [
          ('Brand', 'ยี่ห้อ:', item_vals[1]),
          ('Model', 'รุ่น:', item_vals[2]),
          ('License Plate', 'ทะเบียนรถ:', item_vals[3]),
          ('Type', 'ประเภทรถ:', item_vals[4]),
          ('Year', 'ปีรถ (ค.ศ.):', item_vals[5]),
          ('Color', 'สีรถ:', item_vals[6]),
          (
              'Price Per Day',
              'ราคาเช่าต่อวัน:',
              str(item_vals[7]).replace('฿', '').replace(',', ''),
          ),
      ]
      entries = {}
      for k, label_text, val in fields:
        ttk.Label(dlg, text=label_text, style='White.TLabel').pack(
            anchor=tk.W, padx=25, pady=(4, 0)
        )
        e = ttk.Entry(dlg, width=30)
        e.insert(0, val)
        e.pack(padx=25, pady=(0, 4))
        entries[k] = e

      ttk.Label(dlg, text='สถานะ:', style='White.TLabel').pack(
          anchor=tk.W, padx=25, pady=(4, 0)
      )
      status_cb = ttk.Combobox(
          dlg,
          values=['พร้อมใช้งาน', 'ถูกเช่าอยู่', 'ซ่อมบำรุง'],
          state='readonly',
          width=28,
      )
      status_cb.set(item_vals[8])
      status_cb.pack(padx=25, pady=(0, 4))

      def update():
        try:
          rev_status = {
              'พร้อมใช้งาน': 'AVAILABLE',
              'ถูกเช่าอยู่': 'RENTED',
              'ซ่อมบำรุง': 'MAINTENANCE',
          }
          v = Vehicle(
              vehicle_id=v_id,
              brand=entries['Brand'].get(),
              model=entries['Model'].get(),
              license_plate=entries['License Plate'].get(),
              vehicle_type=entries['Type'].get(),
              year=int(entries['Year'].get()),
              color=entries['Color'].get(),
              price_per_day=float(entries['Price Per Day'].get()),
              status=rev_status.get(status_cb.get(), 'AVAILABLE'),
          )
          if self.vehicle_dao.updateVehicle(v):
            messagebox.showinfo('สำเร็จ', 'อัปเดตข้อมูลรถยนต์เรียบร้อยแล้ว')
            dlg.destroy()
            load_vehicles()
        except Exception as ex:
          messagebox.showerror('ข้อผิดพลาด', f'ข้อมูลไม่ถูกต้อง: {ex}')

      ttk.Button(
          dlg, text='อัปเดตข้อมูล', style='Success.TButton', command=update
      ).pack(pady=15, fill=tk.X, padx=25)

    def delete_vehicle():
      selected = tree.selection()
      if not selected:
        messagebox.showwarning(
            'แจ้งเตือน', 'กรุณาเลือกรายการรถยนต์ที่ต้องการลบ'
        )
        return
      v_id = tree.item(selected[0])['values'][0]
      if messagebox.askyesno(
          'ยืนยัน', 'คุณต้องการลบข้อมูลรถยนต์คันนี้ใช่หรือไม่?'
      ):
        if self.vehicle_dao.deleteVehicle(v_id):
          load_vehicles()

    ttk.Button(
        top_btn_frame,
        text='🔄 รีเฟรช',
        style='Primary.TButton',
        command=load_vehicles,
    ).pack(side=tk.LEFT, padx=5)
    ttk.Button(
        top_btn_frame,
        text='➕ เพิ่มรถยนต์ใหม่',
        style='Success.TButton',
        command=add_vehicle_dialog,
    ).pack(side=tk.LEFT, padx=5)
    ttk.Button(
        top_btn_frame,
        text='✏️ แก้ไขข้อมูลรถ',
        style='Primary.TButton',
        command=edit_vehicle_dialog,
    ).pack(side=tk.LEFT, padx=5)
    ttk.Button(
        top_btn_frame,
        text='🗑️ ลบรถยนต์ที่เลือก',
        style='Danger.TButton',
        command=delete_vehicle,
    ).pack(side=tk.LEFT, padx=5)

    load_vehicles()

  def setup_admin_rentals_tab(self, parent):
    columns = (
        'id',
        'customer',
        'vehicle',
        'license',
        'start',
        'due',
        'return',
        'total_price',
        'status',
    )
    headers = (
        'รหัสเช่า',
        'ชื่อลูกค้า',
        'รุ่นรถ',
        'ทะเบียน',
        'เริ่มเช่า',
        'กำหนดคืน',
        'คืนจริง',
        'ราคารวม',
        'สถานะ',
    )

    tree = ttk.Treeview(parent, columns=columns, show='headings')
    for c, h in zip(columns, headers):
      tree.heading(c, text=h)
      tree.column(c, width=100, anchor=tk.CENTER)

    scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscroll=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    tree.pack(fill=tk.BOTH, expand=True)

    def load_rentals():
      for i in tree.get_children():
        tree.delete(i)
      for r in self.rental_dao.getAllRentals():
        v_name = f"{r['brand']} {r['model']}"
        status_th = STATUS_THAI.get(r['status'], r['status'])
        tree.insert(
            '',
            tk.END,
            values=(
                r['id'],
                r['customer_name'],
                v_name,
                r['license_plate'],
                r['start_date'],
                r['due_date'],
                r['return_date'] or '-',
                f"฿{r['total_price']:,.2f}",
                status_th,
            ),
        )

    def process_return():
      selected = tree.selection()
      if not selected:
        messagebox.showwarning(
            'แจ้งเตือน', 'กรุณาเลือกรายการเช่าที่ต้องการคืนรถ'
        )
        return
      item = tree.item(selected[0])
      r_id, status_th = item['values'][0], item['values'][8]

      if status_th == STATUS_THAI['COMPLETED']:
        messagebox.showinfo(
            'แจ้งเตือน', 'รายการนี้ทำรายการคืนรถเรียบร้อยแล้ว'
        )
        return
      elif status_th == STATUS_THAI['CANCELLED']:
        messagebox.showinfo('แจ้งเตือน', 'รายการนี้ถูกยกเลิกไปแล้ว')
        return

      all_r = self.rental_dao.getAllRentals()
      r_data = next((x for x in all_r if x['id'] == r_id), None)

      if r_data:
        today = date.today()
        due_date = r_data['due_date']
        late_days = (today - due_date).days if today > due_date else 0
        late_fee = late_days * 500.0

        pay_strat = CashPayment()
        if late_fee > 0:
          messagebox.showinfo(
              'คำนวณค่าปรับเกินเวลา',
              f'เกินกำหนด {late_days} วัน!\nค่าปรับที่ต้องชำระเพิ่ม:'
              f' ฿{late_fee:,.2f}',
          )
          method_str = simpledialog.askstring(
              'ชำระค่าปรับ',
              'ช่องทางชำระเงินค่าปรับ (ระบุ: เงินสด / บัตรเครดิต / โอนเงิน):',
          )
          if method_str and (
              'บัตร' in method_str or 'credit' in method_str.lower()
          ):
            pay_strat = CreditCardPayment('4111-XXXX-XXXX-9999')
          elif method_str and (
              'โอน' in method_str or 'bank' in method_str.lower()
          ):
            pay_strat = BankTransferPayment('REF-LATE-888')

        if self.rental_dao.returnVehicle(
            r_id, r_data['vehicle_id'], today, late_days, late_fee, pay_strat
        ):
          messagebox.showinfo(
              'สำเร็จ',
              f'บันทึกรับคืนรถยนต์เรียบร้อย!\nเกินกำหนด: {late_days}'
              f' วัน\nค่าปรับเพิ่มเติม: ฿{late_fee:,.2f}',
          )
          load_rentals()

    def process_admin_cancel():
      selected = tree.selection()
      if not selected:
        messagebox.showwarning(
            'แจ้งเตือน', 'กรุณาเลือกรายการเช่าที่ต้องการยกเลิก'
        )
        return
      item = tree.item(selected[0])
      r_id, status_th = item['values'][0], item['values'][8]

      if status_th != STATUS_THAI['ACTIVE']:
        messagebox.showwarning(
            'แจ้งเตือน',
            'สามารถยกเลิกได้เฉพาะรายการที่อยู่ในสถานะ "กำลังเช่า" เท่านั้น',
        )
        return

      all_r = self.rental_dao.getAllRentals()
      r_data = next((x for x in all_r if x['id'] == r_id), None)

      if r_data and messagebox.askyesno(
          'ยืนยันการยกเลิก', f'คุณต้องการยกเลิกการเช่ารหัส {r_id} ใช่หรือไม่?'
      ):
        if self.rental_dao.cancelRental(r_id, r_data['vehicle_id']):
          messagebox.showinfo(
              'สำเร็จ', 'ยกเลิกรายการเช่าและคืนสถานะรถเรียบร้อยแล้ว'
          )
          load_rentals()

    btn_frame = ttk.Frame(parent)
    btn_frame.pack(fill=tk.X, pady=(10, 0))
    ttk.Button(
        btn_frame,
        text='🔄 รีเฟรชรายการ',
        style='Primary.TButton',
        command=load_rentals,
    ).pack(side=tk.LEFT, padx=5)
    ttk.Button(
        btn_frame,
        text='📥 บันทึกรับคืนรถยนต์ (Return Vehicle)',
        style='Success.TButton',
        command=process_return,
    ).pack(side=tk.LEFT, padx=5)
    ttk.Button(
        btn_frame,
        text='❌ ยกเลิกการเช่า (Cancel)',
        style='Danger.TButton',
        command=process_admin_cancel,
    ).pack(side=tk.LEFT, padx=5)

    load_rentals()

  # --- CUSTOMER DASHBOARD ---
  def show_customer_dashboard(self):
    self.clear_screen()
    cust: Customer = self.current_user

    header = ttk.Frame(self, padding=(15, 10))
    header.pack(fill=tk.X)
    ttk.Label(
        header,
        text=f'👤 บริการเช่ารถยนต์สำหรับลูกค้า (คุณ{cust.get_name()})',
        style='Header.TLabel',
    ).pack(side=tk.LEFT)
    ttk.Button(
        header,
        text='ออกจากระบบ',
        style='Danger.TButton',
        command=self.show_login_frame,
    ).pack(side=tk.RIGHT)

    notebook = ttk.Notebook(self)
    notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

    tab_browse = ttk.Frame(notebook, padding=10)
    tab_history = ttk.Frame(notebook, padding=10)

    notebook.add(tab_browse, text=' 🚘 เลือกรถและทำรายการเช่า ')
    notebook.add(tab_history, text=' 📜 ประวัติการเช่าของฉัน ')

    # --- TAB BROWSE VEHICLES ---
    search_frame = ttk.Frame(tab_browse)
    search_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(search_frame, text='🔍 ค้นหารถ (ยี่ห้อ/รุ่น/ประเภท):').pack(
        side=tk.LEFT, padx=(0, 5)
    )
    search_entry = ttk.Entry(search_frame, width=30)
    search_entry.pack(side=tk.LEFT, padx=5)

    columns = (
        'id',
        'brand',
        'model',
        'license',
        'type',
        'year',
        'color',
        'price_per_day',
        'status',
    )
    headers = (
        'รหัส',
        'ยี่ห้อ',
        'รุ่น',
        'ทะเบียน',
        'ประเภท',
        'ปี',
        'สี',
        'ราคา/วัน',
        'สถานะ',
    )

    tree_frame = ttk.Frame(tab_browse)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    tree = ttk.Treeview(tree_frame, columns=columns, show='headings')
    for c, h in zip(columns, headers):
      tree.heading(c, text=h)
      tree.column(c, width=100, anchor=tk.CENTER)

    scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscroll=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    tree.pack(fill=tk.BOTH, expand=True)

    def load_available():
      for i in tree.get_children():
        tree.delete(i)
      kw = search_entry.get().strip().lower()
      for v in self.vehicle_dao.getAllVehicles():
        status_th = STATUS_THAI.get(v.get_status(), v.get_status())
        full_info = f'{v.get_brand()} {v.get_model()} {v.get_type()}'.lower()
        if not kw or kw in full_info:
          tree.insert(
              '',
              tk.END,
              values=(
                  v.get_id(),
                  v.get_brand(),
                  v.get_model(),
                  v.get_license_plate(),
                  v.get_type(),
                  v.get_year(),
                  v.get_color(),
                  f'฿{v.get_price_per_day():,.2f}',
                  status_th,
              ),
          )

    ttk.Button(
        search_frame, text='ค้นหา', style='Primary.TButton', command=load_available
    ).pack(side=tk.LEFT, padx=5)
    ttk.Button(
        search_frame,
        text='แสดงทั้งหมด',
        style='Primary.TButton',
        command=lambda: [search_entry.delete(0, tk.END), load_available()],
    ).pack(side=tk.LEFT, padx=5)

    def do_rent_vehicle():
      selected = tree.selection()
      if not selected:
        messagebox.showwarning('แจ้งเตือน', 'กรุณาเลือกรถยนต์ที่ต้องการเช่า')
        return

      v_values = tree.item(selected[0])['values']
      v_id, price_str, status_th = v_values[0], str(v_values[7]), v_values[8]

      if status_th != STATUS_THAI['AVAILABLE']:
        messagebox.showerror(
            'ไม่พร้อมใช้งาน', 'รถยนต์คันนี้ไม่พร้อมใช้งานสำหรับการเช่าในขณะนี้'
        )
        return

      price_per_day = float(price_str.replace('฿', '').replace(',', ''))

      days_str = simpledialog.askstring(
          'ระยะเวลาเช่า', 'ต้องการเช่ารถยนต์กี่วัน? (ระบุจำนวนวัน):'
      )
      if not days_str or not days_str.isdigit():
        return

      days = int(days_str)
      if days <= 0:
        return

      total_price = days * price_per_day

      pay_dialog = tk.Toplevel(self)
      pay_dialog.title('เลือกช่องทางการชำระเงิน')
      pay_dialog.geometry('350x250')
      pay_dialog.configure(bg='#FFFFFF')

      # ใช้ Label มาตรฐานเพื่อกำหนดสีตัวอักษรได้ตรงๆ โดยไม่ชนกับ ttk
      lbl_pay = tk.Label(
          pay_dialog,
          text=f'ยอดชำระทั้งหมด: ฿{total_price:,.2f}',
          font=('Tahoma', 14, 'bold'),
          fg='#0D9488',
          bg='#FFFFFF',
      )
      lbl_pay.pack(pady=15)

      def process_pay(method_type):
        pay_dialog.destroy()
        payment_strategy = None
        if method_type == 'CASH':
          payment_strategy = CashPayment()
        elif method_type == 'CREDIT':
          payment_strategy = CreditCardPayment('4111-2222-3333-4444')
        elif method_type == 'BANK':
          payment_strategy = BankTransferPayment('TXN-ONLINE-999')

        start_d = date.today()
        due_d = date.fromordinal(start_d.toordinal() + days)

        if self.rental_dao.createRental(
            cust.get_customer_id(),
            v_id,
            start_d,
            due_d,
            days,
            price_per_day,
            total_price,
            payment_strategy,
        ):
          messagebox.showinfo(
              'สำเร็จ',
              'ทำรายการเช่าสำเร็จ!\nกำหนดคืนรถวันที่:'
              f' {due_d.strftime("%d/%m/%Y")}',
          )
          load_available()
          load_history()

      ttk.Button(
          pay_dialog,
          text='💵 ชำระด้วย เงินสด (Cash)',
          style='Success.TButton',
          command=lambda: process_pay('CASH'),
      ).pack(fill=tk.X, padx=25, pady=4)
      ttk.Button(
          pay_dialog,
          text='💳 ชำระด้วย บัตรเครดิต (Credit Card)',
          style='Primary.TButton',
          command=lambda: process_pay('CREDIT'),
      ).pack(fill=tk.X, padx=25, pady=4)
      ttk.Button(
          pay_dialog,
          text='🏦 ชำระด้วย โอนผ่านธนาคาร (Bank Transfer)',
          style='Primary.TButton',
          command=lambda: process_pay('BANK'),
      ).pack(fill=tk.X, padx=25, pady=4)

    btn_rent = ttk.Button(
        tab_browse,
        text='🔑 ยืนยันทำรายการเช่ารถคันที่เลือก',
        style='Success.TButton',
        command=do_rent_vehicle,
    )
    btn_rent.pack(pady=10)

    load_available()

    # --- TAB HISTORY SETUP ---
    hist_cols = (
        'id',
        'vehicle',
        'license',
        'start',
        'due',
        'return',
        'total_price',
        'status',
    )
    hist_headers = (
        'รหัสเช่า',
        'รถยนต์ที่เช่า',
        'ทะเบียน',
        'วันที่เริ่มเช่า',
        'กำหนดคืน',
        'คืนจริง',
        'ยอดรวม',
        'สถานะ',
    )

    tree_hist_frame = ttk.Frame(tab_history)
    tree_hist_frame.pack(fill=tk.BOTH, expand=True)

    tree_hist = ttk.Treeview(tree_hist_frame, columns=hist_cols, show='headings')
    for c, h in zip(hist_cols, hist_headers):
      tree_hist.heading(c, text=h)
      tree_hist.column(c, width=110, anchor=tk.CENTER)

    scrollbar_hist = ttk.Scrollbar(
        tree_hist_frame, orient=tk.VERTICAL, command=tree_hist.yview
    )
    tree_hist.configure(yscroll=scrollbar_hist.set)
    scrollbar_hist.pack(side=tk.RIGHT, fill=tk.Y)
    tree_hist.pack(fill=tk.BOTH, expand=True, pady=5)

    def load_history():
      for i in tree_hist.get_children():
        tree_hist.delete(i)
      for r in self.rental_dao.getRentalsByCustomer(cust.get_customer_id()):
        v_info = f"{r['brand']} {r['model']}"
        status_th = STATUS_THAI.get(r['status'], r['status'])
        tree_hist.insert(
            '',
            tk.END,
            values=(
                r['id'],
                v_info,
                r['license_plate'],
                r['start_date'],
                r['due_date'],
                r['return_date'] or '-',
                f"฿{r['total_price']:,.2f}",
                status_th,
            ),
        )

    def process_customer_cancel():
      selected = tree_hist.selection()
      if not selected:
        messagebox.showwarning(
            'แจ้งเตือน', 'กรุณาเลือกรายการเช่าที่ต้องการยกเลิก'
        )
        return

      item_vals = tree_hist.item(selected[0])['values']
      r_id, status_th = item_vals[0], item_vals[7]

      if status_th != STATUS_THAI['ACTIVE']:
        messagebox.showwarning(
            'แจ้งเตือน',
            'คุณสามารถยกเลิกได้เฉพาะรายการที่อยู่ในสถานะ "กำลังเช่า" เท่านั้น',
        )
        return

      user_rentals = self.rental_dao.getRentalsByCustomer(cust.get_customer_id())
      r_data = next((x for x in user_rentals if x['id'] == r_id), None)

      if r_data and messagebox.askyesno(
          'ยืนยันการยกเลิก',
          f'คุณต้องการยกเลิกการเช่ารถรายการรหัส {r_id} ใช่หรือไม่?',
      ):
        if self.rental_dao.cancelRental(r_id, r_data['vehicle_id']):
          messagebox.showinfo('สำเร็จ', 'ยกเลิกรายการเช่ารถยนต์เรียบร้อยแล้ว')
          load_history()
          load_available()

    btn_hist_frame = ttk.Frame(tab_history)
    btn_hist_frame.pack(fill=tk.X, pady=(5, 0))

    ttk.Button(
        btn_hist_frame,
        text='🔄 รีเฟรชประวัติ',
        style='Primary.TButton',
        command=load_history,
    ).pack(side=tk.LEFT, padx=5)

    ttk.Button(
        btn_hist_frame,
        text='❌ ยกเลิกรายการเช่านี้',
        style='Danger.TButton',
        command=process_customer_cancel,
    ).pack(side=tk.LEFT, padx=5)

    load_history()


# ==========================================
# 7. MAIN PROGRAM ENTRY POINT
# ==========================================
if __name__ == '__main__':
  app = MainApplication()
  app.mainloop()