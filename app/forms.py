from flask_wtf import FlaskForm
from wtforms import BooleanField, DecimalField, EmailField, IntegerField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional


class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(max=128)])
    remember = BooleanField("Remember me")
    submit = SubmitField("Sign in")


class RegisterForm(FlaskForm):
    business_name = StringField("Business name", validators=[DataRequired(), Length(max=140)])
    owner_name = StringField("Your name", validators=[DataRequired(), Length(max=120)])
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=10, max=128)])
    confirm = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Create business")


class ProductForm(FlaskForm):
    name = StringField("Product name", validators=[DataRequired(), Length(max=160)])
    sku = StringField("SKU / code", validators=[DataRequired(), Length(max=80)])
    buy_price = DecimalField("Cost price", places=2, validators=[DataRequired(), NumberRange(min=0, max=99999999)])
    sell_price = DecimalField("Selling price", places=2, validators=[DataRequired(), NumberRange(min=0, max=99999999)])
    qty = IntegerField("Opening stock", validators=[DataRequired(), NumberRange(min=0)])
    low_stock_threshold = IntegerField("Low stock alert at", validators=[DataRequired(), NumberRange(min=0)])
    category = StringField("Category", validators=[Optional(), Length(max=80)])
    submit = SubmitField("Save product")


class CustomerForm(FlaskForm):
    name = StringField("Customer name", validators=[DataRequired(), Length(max=140)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    email = EmailField("Email", validators=[Optional(), Email(), Length(max=255)])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Save customer")


class ExpenseForm(FlaskForm):
    title = StringField("Expense", validators=[DataRequired(), Length(max=160)])
    category = StringField("Category", validators=[DataRequired(), Length(max=80)])
    amount = DecimalField("Amount", places=2, validators=[DataRequired(), NumberRange(min=0.01, max=99999999)])
    note = TextAreaField("Note", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Save expense")


class StaffForm(FlaskForm):
    name = StringField("Staff name", validators=[DataRequired(), Length(max=120)])
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Temporary password", validators=[DataRequired(), Length(min=10, max=128)])
    role = SelectField("Role", choices=[("manager", "Manager"), ("cashier", "Cashier")], validators=[DataRequired()])
    submit = SubmitField("Add staff")


class BusinessForm(FlaskForm):
    name = StringField("Business name", validators=[DataRequired(), Length(max=140)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    address = StringField("Address", validators=[Optional(), Length(max=240)])
    submit = SubmitField("Save settings")
