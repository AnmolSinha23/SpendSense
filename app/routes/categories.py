"""
SpendSense - Categories Management Route
Handles default global categories and user-specific custom categories.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.db import query_db
from app.routes.auth import login_required

categories_bp = Blueprint('categories', __name__)


@categories_bp.route('/categories')
@login_required
def list_categories():
    """
    Displays list of default system categories and user-created custom categories.
    """
    user_id = session['user_id']

    # Fetch default categories (user_id IS NULL)
    default_categories = query_db(
        """
        SELECT category_id, category_name, category_type, icon
        FROM categories
        WHERE user_id IS NULL
        ORDER BY category_type DESC, category_name ASC
        """
    )

    # Fetch user custom categories (user_id = current user)
    custom_categories = query_db(
        """
        SELECT
            c.category_id,
            c.category_name,
            c.category_type,
            c.icon,
            COUNT(t.transaction_id) AS txn_count
        FROM categories c
        LEFT JOIN transactions t ON c.category_id = t.category_id
        WHERE c.user_id = %s
        GROUP BY c.category_id, c.category_name, c.category_type, c.icon
        ORDER BY c.category_name ASC
        """,
        (user_id,)
    )

    return render_template(
        'categories.html',
        default_categories=default_categories,
        custom_categories=custom_categories
    )


@categories_bp.route('/categories/add', methods=['POST'])
@login_required
def add_category():
    """
    Creates a new custom category for the authenticated user.
    """
    user_id = session['user_id']
    category_name = request.form.get('category_name', '').strip()
    category_type = request.form.get('category_type', 'expense').strip()
    icon = request.form.get('icon', 'bi-tag').strip()

    if not category_name:
        flash("Category name cannot be empty.", "danger")
        return redirect(url_for('categories.list_categories'))

    if category_type not in ('income', 'expense'):
        flash("Invalid category type.", "danger")
        return redirect(url_for('categories.list_categories'))

    # Check for duplicate category name for this user or in defaults
    existing = query_db(
        """
        SELECT category_id FROM categories
        WHERE category_name = %s AND (user_id IS NULL OR user_id = %s)
        """,
        (category_name, user_id),
        one=True
    )
    if existing:
        flash(f"A category named '{category_name}' already exists.", "warning")
        return redirect(url_for('categories.list_categories'))

    try:
        query_db(
            """
            INSERT INTO categories (user_id, category_name, category_type, icon)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, category_name, category_type, icon),
            commit=True
        )
        flash(f"Custom category '{category_name}' added successfully!", "success")
    except Exception as e:
        flash(f"Error creating category: {str(e)}", "danger")

    return redirect(url_for('categories.list_categories'))


@categories_bp.route('/categories/<int:category_id>/delete', methods=['POST'])
@login_required
def delete_category(category_id):
    """
    Deletes a user custom category (cannot delete global default categories).
    Enforces referential integrity by checking if transactions reference it.
    """
    user_id = session['user_id']

    # Ensure category belongs to this user
    cat = query_db(
        "SELECT user_id, category_name FROM categories WHERE category_id = %s",
        (category_id,),
        one=True
    )
    if not cat:
        flash("Category not found.", "danger")
        return redirect(url_for('categories.list_categories'))

    if cat['user_id'] != user_id:
        flash("Default system categories cannot be deleted.", "warning")
        return redirect(url_for('categories.list_categories'))

    # Check if category is currently referenced in transactions
    usage = query_db(
        "SELECT COUNT(*) AS cnt FROM transactions WHERE category_id = %s",
        (category_id,),
        one=True
    )
    if usage and usage['cnt'] > 0:
        flash(f"Cannot delete category '{cat['category_name']}' because it is linked to {usage['cnt']} existing transaction(s).", "warning")
        return redirect(url_for('categories.list_categories'))

    try:
        query_db(
            "DELETE FROM categories WHERE category_id = %s AND user_id = %s",
            (category_id, user_id),
            commit=True
        )
        flash(f"Category '{cat['category_name']}' deleted successfully.", "info")
    except Exception as e:
        flash(f"Error deleting category: {str(e)}", "danger")

    return redirect(url_for('categories.list_categories'))
