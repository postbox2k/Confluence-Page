import os
import json
from flask import (
    Flask, request, redirect, url_for, render_template_string,
    send_from_directory, abort, session, flash
)
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.secret_key = 'replace_with_a_very_secret_key'  # Change in prod

# Config
BASE_DATA_DIR = 'wiki_pages'  # base parent directory containing user spaces
IMG_DIR = 'wiki_images'
USERS_FILE = 'users.json'  # store registered users here, super user not stored here

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
SUPER_USER = 'Postman'  # globally hidden super user

# Create necessary dirs if missing
os.makedirs(BASE_DATA_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

# Load users.json or create default
def load_users():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump([], f)
        return []
    with open(USERS_FILE, 'r') as f:
        try:
            users = json.load(f)
            if not isinstance(users, list):
                return []
            return users
        except:
            return []
def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)
users_list = load_users()

# Helper to create user space dir if missing
def ensure_user_space(username):
    user_dir = os.path.join(BASE_DATA_DIR, username)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    return user_dir

# Ensure spaces for all users on load
for user in users_list:
    ensure_user_space(user)
ensure_user_space(SUPER_USER)  # super user space exists too

# Access control decorators
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'username' not in session:
            flash('Please login first.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return wrap

def user_can_edit(username, target_user):
    """Return True if username can edit target_user space pages."""
    if username == SUPER_USER:
        return True
    return username == target_user

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

# Helper: list pages in given user space
def list_pages(user):
    user_dir = ensure_user_space(user)
    files = [f for f in os.listdir(user_dir) if f.endswith('.html')]
    return sorted([os.path.splitext(f)[0] for f in files], key=str.lower)

# Load page content per user space
def load_page(username, page_name):
    user_dir = ensure_user_space(username)
    path = os.path.join(user_dir, f"{page_name}.html")
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        return None

# Save page content per user space
def save_page(username, page_name, content):
    user_dir = ensure_user_space(username)
    path = os.path.join(user_dir, f"{page_name}.html")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# Delete page
def delete_page(username, page_name):
    user_dir = ensure_user_space(username)
    path = os.path.join(user_dir, f"{page_name}.html")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False

# Context processor inject common variables
@app.context_processor
def inject_user_and_pages():
    current_user = session.get('username')
    # For super user, current_space can be selected via query param 'space' or defaults to super user own space
    if current_user == SUPER_USER:
        current_space = request.args.get('space', SUPER_USER)
        # Validate current_space
        if current_space != SUPER_USER and current_space not in users_list:
            current_space = SUPER_USER
        user_list_for_select = [SUPER_USER] + users_list
    elif current_user:
        current_space = current_user
        user_list_for_select = [current_user]
    else:
        # For visitors (not logged in), show only super user space for viewing
        current_user = None
        current_space = SUPER_USER
        user_list_for_select = []

    pages = list_pages(current_space) if current_space else []

    # Hide super user name from UI: show only "Super User"
    display_username = None
    if current_user == SUPER_USER:
        display_username = 'Super User'
    elif current_user:
        display_username = current_user

    return dict(
        username=current_user,
        display_username=display_username,
        current_space=current_space,
        pages=pages,
        all_users=user_list_for_select,
        super_user=SUPER_USER
    )

# Templates with sidebar/ navbar and auth

BASE_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{{ title }}</title>
<!-- Bootstrap CSS -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet" crossorigin="anonymous"/>
<!-- Bootstrap Icons -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css" rel="stylesheet" />
<style>
  :root {
    --primary-color: #0052cc;
    --secondary-color: #172b4d;
    --bg-color: #f4f5f7;
    --content-bg: #ffffff;
    --text-color: #172b4d;
    --link-color: #0052cc;
    --border-color: #dfe1e6;
  }
  body {
    padding-top: 56px;
    font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
    background-color: var(--bg-color);
    color: var(--text-color);
    transition: padding-top 0.3s ease;
  }
  .navbar {
    background-color: var(--primary-color) !important;
    box-shadow: 0 2px 4px rgb(0 0 0 / 0.1);
    transition: top 0.3s ease, height 0.3s ease, padding 0.3s ease;
  }
  .navbar.minimized {
    height: 2.5rem !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    overflow: hidden;
  }
  .navbar-brand {
    font-weight: 700;
    font-size: 1.5rem;
    color: white !important;
    transition: opacity 0.3s ease;
  }
  .navbar.minimized .navbar-brand {
    opacity: 0;
    pointer-events: none;
  }
  .navbar-brand:hover {
    color: #c2d4ff !important;
    text-decoration: none;
  }
  a, a:hover {
    color: var(--link-color);
    text-decoration: none;
  }
  .container-fluid {
    padding-left: 0;
    padding-right: 0;
    max-width: 100vw;
  }
  .content-area {
    padding: 2rem;
    background: var(--content-bg);
    border-radius: 6px;
    box-shadow: 0 1px 3px rgb(9 30 66 / 0.25);
    border: 1px solid var(--border-color);
    margin-bottom: 3rem;
    min-height: 80vh;
    overflow-wrap: break-word;
  }
  h1 {
    font-weight: 600;
    margin-bottom: 1rem;
    color: var(--secondary-color);
  }
  .btn-primary {
    background-color: var(--primary-color);
    border-color: var(--primary-color);
  }
  .btn-primary:hover {
    background-color: #003d99;
    border-color: #003d99;
  }
  .btn-secondary {
    border-radius: 6px;
  }
  .btn-outline-primary {
    color: var(--primary-color);
    border-color: var(--primary-color);
  }
  .btn-outline-primary:hover {
    background-color: var(--primary-color);
    color: white;
  }
  .btn-outline-danger {
    color: #de350b;
    border-color: #de350b;
  }
  .btn-outline-danger:hover {
    background-color: #de350b;
    color: white;
  }
  textarea {
    font-family: monospace;
    border: 1px solid var(--border-color);
    border-radius: 6px;
  }
  .search-bar .input-group-text {
    background-color: white;
    border: 1px solid var(--border-color);
    border-right: none;
  }
  .search-bar input.form-control {
    border-radius: 6px 0 0 6px;
    border-right: none;
  }
  .search-bar button {
    border-radius: 0 6px 6px 0;
  }
  .breadcrumb {
    background: none;
    padding-left: 0;
    margin-bottom: 1rem;
  }
  .breadcrumb-item + .breadcrumb-item::before {
    content: ">";
  }
  .content img {
    max-width: 100%;
    border-radius: 4px;
    box-shadow: 0 1px 3px rgb(9 30 66 / 0.15);
  }
  .alert {
    border-radius: 6px;
  }
  /* Sidebar */
  #sidebar {
    position: fixed;
    top: 56px;
    left: 0;
    height: calc(100vh - 56px);
    width: 280px;
    background: white;
    border-right: 1px solid var(--border-color);
    overflow-y: auto;
    padding: 1rem;
    z-index: 1030;
    transition: top 0.3s ease;
  }
  #sidebar.minimized {
    top: 2.5rem;
    height: calc(100vh - 2.5rem);
  }
  #sidebar h5 {
    font-weight: 600;
    margin-bottom: 1rem;
    color: var(--secondary-color);
  }
  #sidebar ul {
    list-style: none;
    padding-left: 0;
  }
  #sidebar ul li {
    margin-bottom: 0.5rem;
  }
  #sidebar ul li a {
    color: var(--primary-color);
    text-decoration: none;
    display: block;
    padding: 0.4rem 0.6rem;
    border-radius: 4px;
  }
  #sidebar ul li a.active,
  #sidebar ul li a:hover {
    background-color: var(--primary-color);
    color: white;
    text-decoration: none;
  }
  /* Main content next to sidebar */
  #main-content {
    margin-left: 290px;
    padding: 2rem 2.5rem 3rem 2.5rem;
    max-width: 960px;
    background: var(--content-bg);
    border-radius: 6px;
    box-shadow: 0 1px 3px rgb(9 30 66 / 0.25);
    min-height: 80vh;
    overflow-wrap: break-word;
    transition: margin-top 0.3s ease;
  }
  #main-content.minimized {
    margin-top: 2.5rem; /* adjusted for minimized navbar */
  }
  /* Navbar right */
  .navbar-nav.ml-auto {
    margin-left: auto;
  }
  /* User space selector dropdown for super user */
  #spaceSelectForm select {
    border-radius: 6px;
    border: 1px solid var(--border-color);
    padding: 0.25rem 0.5rem;
    min-width: 140px;
  }
  /* Collapsible section toggle button */
  .section-header {
    display: flex;
    align-items: center;
    cursor: pointer;
    user-select: none;
  }
  .toggle-btn {
    margin-left: auto;
    background-color: var(--primary-color);
    border: none;
    color: white;
    border-radius: 4px;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    line-height: 1;
  }
  .toggle-btn:hover {
    background-color: #003d99;
  }
  /* Navbar minimize button */
  #navbarMinimizeBtn {
    background-color: transparent;
    border: none;
    color: white;
    font-size: 1.25rem;
    display: flex;
    align-items: center;
    cursor: pointer;
    margin-left: 0.75rem;
  }
  #navbarMinimizeBtn:hover {
    color: #c2d4ff;
  }
</style>
</head>
<body>
<nav class="navbar fixed-top navbar-expand-lg">
  <div class="container d-flex align-items-center">
    <a class="navbar-brand" href="{{ url_for('index') }}">
      <i class="bi bi-journal-text"></i> RBC CCAR Developers Confluence
    </a>
    <button id="navbarMinimizeBtn" title="Minimize navbar" aria-expanded="true" aria-label="Toggle navbar minimize">
      <i class="bi bi-chevron-up"></i>
    </button>
    <div class="d-flex align-items-center ms-auto">
      {% if username %}
        <span class="me-3 text-white">Hello, <strong>{{ display_username }}</strong></span>
        {% if username == super_user %}
          <!-- show space selector for super user -->
          <form id="spaceSelectForm" method="GET" action="{{ url_for('index') }}" class="me-3 d-inline-block">
            <select name="space" onchange="this.form.submit()" aria-label="Select user space">
              {% for useropt in all_users %}
              <option value="{{ useropt }}" {% if useropt == current_space %}selected{% endif %}>
                {{ 'Super User' if useropt==super_user else useropt }}
              </option>
              {% endfor %}
            </select>
          </form>
          <a href="{{ url_for('manage_users') }}" class="btn btn-outline-light btn-sm me-2" title="Manage Users">
            <i class="bi bi-people"></i> Users
          </a>
        {% endif %}
        <a href="{{ url_for('logout') }}" class="btn btn-outline-light btn-sm">
          <i class="bi bi-box-arrow-right"></i> Logout
        </a>
      {% else %}
        <a href="{{ url_for('login') }}" class="btn btn-outline-light btn-sm">
          <i class="bi bi-box-arrow-in-right"></i> Login
        </a>
      {% endif %}
    </div>
  </div>
</nav>

<div id="sidebar" aria-label="Page navigation">
  <h5>{{ 'Pages in '+current_space if current_space else 'Pages' }}</h5>
  <ul>
    {% for page in pages %}
    <li>
      <a href="{{ url_for('view_page', page_name=page, space=current_space) }}"
         class="{% if page == current_page %}active{% endif %}">{{ page }}</a>
    </li>
    {% endfor %}
    {% if username and user_can_edit(username, current_space) %}
    <li><a href="{{ url_for('new_page', space=current_space) }}"><i class="bi bi-plus-circle"></i> New Page</a></li>
    {% endif %}
  </ul>
</div>

<div id="main-content" role="main">
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      {% for category, message in messages %}
      <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
        {{ message }}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
      </div>
      {% endfor %}
    {% endif %}
  {% endwith %}
  {{ body|safe }}
</div>

<!-- Bootstrap JS Bundle -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js" crossorigin="anonymous"></script>

<!-- Section toggle script -->
<script>
document.addEventListener('DOMContentLoaded', function() {
    const contentDiv = document.querySelector('.content');
    if (!contentDiv) return;

    const headings = contentDiv.querySelectorAll('h2');
    headings.forEach(heading => {
        const toggleBtn = document.createElement('button');
        toggleBtn.classList.add('toggle-btn');
        toggleBtn.setAttribute('aria-label', 'Toggle section');
        toggleBtn.innerHTML = '&#x2212;'; // minus sign, initially expanded

        const wrapper = document.createElement('div');
        wrapper.classList.add('section-header');
        while (heading.firstChild) {
          wrapper.appendChild(heading.firstChild);
        }
        heading.textContent = '';
        heading.appendChild(wrapper);
        wrapper.appendChild(toggleBtn);

        let sectionContent = [];
        let sibling = heading.nextElementSibling;
        while (sibling && sibling.tagName.toLowerCase() !== 'h2') {
            sectionContent.push(sibling);
            sibling = sibling.nextElementSibling;
        }

        toggleBtn.addEventListener('click', () => {
            const isCollapsed = toggleBtn.innerHTML === '+';
            if (isCollapsed) {
                toggleBtn.innerHTML = '&#x2212;';
                sectionContent.forEach(el => el.style.display = '');
            } else {
                toggleBtn.innerHTML = '+';
                sectionContent.forEach(el => el.style.display = 'none');
            }
        });
    });

    // Navbar minimize toggle
    const nav = document.querySelector('nav.navbar');
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');
    const btn = document.getElementById('navbarMinimizeBtn');
    if (nav && sidebar && mainContent && btn) {
        btn.addEventListener('click', () => {
            const minimized = nav.classList.toggle('minimized');
            sidebar.classList.toggle('minimized', minimized);
            mainContent.classList.toggle('minimized', minimized);
            // Change icon and aria-expanded attribute
            if (minimized) {
                btn.innerHTML = '<i class="bi bi-chevron-down"></i>';
                btn.setAttribute('aria-expanded', 'false');
                btn.setAttribute('title', 'Maximize navbar');
            } else {
                btn.innerHTML = '<i class="bi bi-chevron-up"></i>';
                btn.setAttribute('aria-expanded', 'true');
                btn.setAttribute('title', 'Minimize navbar');
            }
        });
    }
});
</script>

</body>
</html>
'''

# Other unchanged templates (INDEX_BODY, VIEW_PAGE_BODY, EDIT_PAGE_BODY, NEW_PAGE_BODY, LOGIN_BODY) still present here as before...

# NOTE: For brevity, I'm only explicitly rewriting the BASE_HTML here, all other routes and templates remain unchanged from prior code.

# Routes and other code section remain unchanged from the prior code.
# Just the BASE_HTML and inline script stylistic and functional updates included.


INDEX_BODY = '''
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1>Pages</h1>
</div>
<form method="GET" action="{{ url_for('index') }}" class="mb-4 search-bar">
  <input type="hidden" name="space" value="{{ current_space }}">
  <div class="input-group">
    <input type="text" name="q" value="{{ query }}" class="form-control" placeholder="Search pages..." aria-label="Search pages" />
    <button class="btn btn-outline-primary" type="submit"><i class="bi bi-search"></i></button>
    {% if query %}
      <a href="{{ url_for('index', space=current_space) }}" class="btn btn-outline-danger ms-2" title="Clear search"><i class="bi bi-x-circle"></i></a>
    {% endif %}
  </div>
</form>
{% if pages %}
<ul class="list-group list-group-flush">
  {% for page in pages %}
  <li class="list-group-item d-flex justify-content-between align-items-center">
    <a href="{{ url_for('view_page', page_name=page, space=current_space) }}" class="fw-semibold">{{ page }}</a>
    <span>
      {% if username and user_can_edit(username, current_space) %}
      <a href="{{ url_for('edit_page', page_name=page, space=current_space) }}" class="btn btn-sm btn-outline-primary me-2" title="Edit">
        <i class="bi bi-pencil"></i>
      </a>
      <form action="{{ url_for('delete_page_route', page_name=page, space=current_space) }}" method="POST" style="display:inline;" onsubmit="return confirm('Delete page {{page}}?');">
        <button type="submit" class="btn btn-sm btn-outline-danger" title="Delete">
          <i class="bi bi-trash"></i>
        </button>
      </form>
      {% endif %}
    </span>
  </li>
  {% endfor %}
</ul>
{% else %}
<p class="text-muted fs-5">No pages found.</p>
{% endif %}
'''

VIEW_PAGE_BODY = '''
<nav aria-label="breadcrumb">
  <ol class="breadcrumb">
    <li class="breadcrumb-item"><a href="{{ url_for('index', space=current_space) }}">Home</a></li>
    <li class="breadcrumb-item active" aria-current="page">{{ page_name }}</li>
  </ol>
</nav>
<div class="content-area">
  <h1 class="mb-4">{{ page_name }}</h1>
  <div class="content">
    {{ content | safe }}
  </div>
</div>
{% if username and user_can_edit(username, current_space) %}
<a href="{{ url_for('edit_page', page_name=page_name, space=current_space) }}" class="btn btn-primary me-2">
  <i class="bi bi-pencil-square"></i> Edit Page
</a>
{% endif %}
<a href="{{ url_for('index', space=current_space) }}" class="btn btn-secondary">
  <i class="bi bi-house-door"></i> Back to Index
</a>
'''

EDIT_PAGE_BODY = '''
<h1 class="mb-4">Edit Page: {{ page_name }}</h1>
<form method="POST" enctype="multipart/form-data" class="mb-3">
  <div class="mb-4">
    <label for="content" class="form-label">Content (HTML supported)</label>
    <textarea name="content" id="content" rows="15" class="form-control" required>{{ content }}</textarea>
  </div>
  <div class="mb-4">
    <label for="image" class="form-label">Upload Image</label>
    <input class="form-control" type="file" id="image" name="image" accept="image/*" />
  </div>
  <button type="submit" class="btn btn-success me-2">
    <i class="bi bi-save"></i> Save
  </button>
  <a href="{{ url_for('view_page', page_name=page_name, space=current_space) }}" class="btn btn-secondary">
    <i class="bi bi-x-lg"></i> Cancel
  </a>
</form>
{% if messages %}
  <div class="alert alert-info" role="alert">
    {{ messages }}
  </div>
{% endif %}
<p class="mt-3">To include an uploaded image in your content, use this format:</p>
<pre>&lt;img src="/images/your_image_filename.ext"&gt;</pre>
'''

NEW_PAGE_BODY = '''
<h1 class="mb-4">Create New Page</h1>
<form method="POST" class="mb-3">
  <input type="hidden" name="space" value="{{ current_space }}">
  <div class="mb-3">
    <label for="page_name" class="form-label">Page Name</label>
    <input type="text" name="page_name" id="page_name" class="form-control" required pattern="[^/\\s]+" title="No spaces or slashes" autofocus />
  </div>
  <button type="submit" class="btn btn-success">
    <i class="bi bi-plus-circle"></i> Create
  </button>
  <a href="{{ url_for('index', space=current_space) }}" class="btn btn-secondary ms-2">
    <i class="bi bi-x-lg"></i> Cancel
  </a>
</form>
{% if messages %}
  <div class="alert alert-danger" role="alert">
    {{ messages }}
  </div>
{% endif %}
'''

LOGIN_BODY = '''
<h1 class="mb-4">Login</h1>
<form method="POST" class="mb-3" novalidate>
  <div class="mb-3">
    <label for="username" class="form-label">Username</label>
    <input type="text" name="username" id="username" class="form-control" required autofocus/>
    <div class="form-text">No password needed. Contact super user for registration.</div>
  </div>
  <button type="submit" class="btn btn-primary">
    <i class="bi bi-box-arrow-in-right"></i> Login
  </button>
</form>
{% if messages %}
  <div class="alert alert-danger" role="alert">
    {{ messages }}
  </div>
{% endif %}
'''

# Routes

@app.route('/')
def index():
    # Determine acting user and space
    current_user = session.get('username')
    # Super user can select space by query parameter
    space = request.args.get('space')
    if current_user == SUPER_USER:
        if space not in [SUPER_USER] + users_list:
            space = SUPER_USER
    else:
        # Visitors and normal users default to super user space if not logged in or no other space
        if not current_user:
            space = SUPER_USER
        else:
            space = current_user

    query = request.args.get('q', '').strip()
    pages = list_pages(space)
    if query:
        pages = [p for p in pages if query.lower() in p.lower()]

    body = render_template_string(INDEX_BODY, pages=pages, query=query, current_space=space, username=current_user, user_can_edit=user_can_edit)
    return render_template_string(BASE_HTML, title="Home - Personal Wiki", body=body, current_space=space,
                                  username=current_user,
                                  display_username='Super User' if current_user==SUPER_USER else current_user,
                                  all_users=[SUPER_USER]+users_list, super_user=SUPER_USER)

@app.route('/page/<page_name>')
def view_page(page_name):
    current_user = session.get('username')
    space = request.args.get('space')
    if current_user == SUPER_USER:
        if space not in [SUPER_USER] + users_list:
            space = SUPER_USER
    else:
        if not current_user:
            space = SUPER_USER
        else:
            space = current_user

    content = load_page(space, page_name)
    if content is None:
        abort(404)

    body = render_template_string(VIEW_PAGE_BODY, page_name=page_name, content=content, current_space=space,
                                  username=current_user, user_can_edit=user_can_edit)
    return render_template_string(BASE_HTML, title=page_name, body=body, current_space=space,
                                  username=current_user,
                                  display_username='Super User' if current_user==SUPER_USER else current_user,
                                  all_users=[SUPER_USER]+users_list, super_user=SUPER_USER)

@app.route('/edit/<page_name>', methods=['GET','POST'])
@login_required
def edit_page(page_name):
    current_user = session.get('username')
    space = request.args.get('space')
    if current_user == SUPER_USER:
        if space not in [SUPER_USER] + users_list:
            space = SUPER_USER
    else:
        if not current_user:
            flash('Please login first.', 'warning')
            return redirect(url_for('login'))
        else:
            space = current_user

    if not user_can_edit(current_user, space):
        flash('You do not have permission to edit pages in this space.', 'danger')
        return redirect(url_for('view_page', page_name=page_name, space=space))

    messages = ''
    if request.method == 'POST':
        content = request.form.get('content', '')
        save_page(space, page_name, content)
        if 'image' in request.files:
            img = request.files['image']
            if img and img.filename != '' and allowed_image(img.filename):
                filename = secure_filename(img.filename)
                img.save(os.path.join(IMG_DIR, filename))
                messages = f'Image "{filename}" uploaded successfully. Add it in content as &lt;img src="/images/{filename}"&gt;.'
            elif img and img.filename != '':
                messages = 'File type not allowed for image upload.'
        if not messages:
            flash('Page saved successfully.', 'success')
            return redirect(url_for('view_page', page_name=page_name, space=space))
    else:
        content = load_page(space, page_name) or ''

    body = render_template_string(EDIT_PAGE_BODY, page_name=page_name, content=content, messages=messages, current_space=space)
    return render_template_string(BASE_HTML, title=f"Edit {page_name}", body=body,
                                  current_space=space, username=current_user,
                                  display_username='Super User' if current_user==SUPER_USER else current_user,
                                  all_users=[SUPER_USER]+users_list, super_user=SUPER_USER)

@app.route('/new', methods=['GET','POST'])
@login_required
def new_page():
    current_user = session.get('username')
    space = request.args.get('space')
    if current_user == SUPER_USER:
        if space not in [SUPER_USER] + users_list:
            space = SUPER_USER
    else:
        if not current_user:
            flash('Please login first.', 'warning')
            return redirect(url_for('login'))
        else:
            space = current_user

    if not user_can_edit(current_user, space):
        flash('You do not have permission to add pages in this space.', 'danger')
        return redirect(url_for('index', space=space))

    messages = ''
    if request.method == 'POST':
        page_name = request.form.get('page_name', '').strip()
        if not page_name or any(c in page_name for c in ' /\\'):
            messages = 'Page name cannot be empty or contain spaces or slashes.'
        elif page_name in list_pages(space):
            messages = 'Page already exists. Choose a different name.'
        else:
            save_page(space, page_name, '<p>Your content here</p>')
            flash(f'Page "{page_name}" created successfully.', 'success')
            return redirect(url_for('view_page', page_name=page_name, space=space))
    body = render_template_string(NEW_PAGE_BODY, messages=messages, current_space=space)
    return render_template_string(BASE_HTML, title="Create New Page", body=body, current_space=space,
                                  username=current_user,
                                  display_username='Super User' if current_user==SUPER_USER else current_user,
                                  all_users=[SUPER_USER]+users_list, super_user=SUPER_USER)

@app.route('/delete/<page_name>', methods=['POST'])
@login_required
def delete_page_route(page_name):
    current_user = session.get('username')
    space = request.args.get('space')
    if current_user == SUPER_USER:
        if space not in [SUPER_USER] + users_list:
            space = SUPER_USER
    else:
        if not current_user:
            flash('Please login first.', 'warning')
            return redirect(url_for('login'))
        else:
            space = current_user

    if not user_can_edit(current_user, space):
        flash('You do not have permission to delete pages in this space.', 'danger')
        return redirect(url_for('view_page', page_name=page_name, space=space))

    deleted = delete_page(space, page_name)
    if deleted:
        flash(f'Page "{page_name}" deleted.', 'success')
    else:
        flash('Page not found.', 'danger')
    return redirect(url_for('index', space=space))

@app.route('/images/<filename>')
def images(filename):
    return send_from_directory(IMG_DIR, filename)

@app.route('/login', methods=['GET','POST'])
def login():
    messages = ''
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        if not username:
            messages = 'Please enter a username.'
        elif username != SUPER_USER and username not in users_list:
            messages = 'Username not registered. Contact super user for registration.'
        else:
            session['username'] = username
            flash(f'Logged in as {"Super User" if username==SUPER_USER else username}', 'success')
            next_url = request.args.get('next') or url_for('index')
            return redirect(next_url)
    body = render_template_string(LOGIN_BODY, messages=messages)
    return render_template_string(BASE_HTML, title='Login', body=body,
                                  current_space=None, username=None,
                                  display_username=None, all_users=[SUPER_USER]+users_list,
                                  super_user=SUPER_USER)

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Admin user management page: only super user allowed
@app.route('/admin/users', methods=['GET','POST'])
@login_required
def manage_users():
    if session.get('username') != SUPER_USER:
        flash('You do not have permission to access that page.', 'danger')
        return redirect(url_for('index'))

    messages = ''
    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username', '').strip()
        global users_list
        if action == 'add':
            if not username:
                messages = 'Enter a username to add.'
            elif username == SUPER_USER:
                messages = 'Cannot add super user.'
            elif username in users_list:
                messages = 'User already exists.'
            else:
                users_list.append(username)
                save_users(users_list)
                ensure_user_space(username)
                flash(f'User "{username}" added.', 'success')
                return redirect(url_for('manage_users'))
        elif action == 'remove':
            if username in users_list:
                # Delete user's space directory and contents recursively
                user_space_path = os.path.join(BASE_DATA_DIR, username)
                if os.path.exists(user_space_path) and os.path.isdir(user_space_path):
                    import shutil
                    shutil.rmtree(user_space_path)
                users_list.remove(username)
                save_users(users_list)
                flash(f'User "{username}" removed.', 'success')
                return redirect(url_for('manage_users'))
            else:
                messages = f'User "{username}" not found.'

    # Show user list excluding super user
    users_show = users_list[:]

    ADMIN_USERS_BODY = '''
    <h1 class="mb-4">User Management</h1>
    <form method="POST" class="mb-4">
      <div class="input-group mb-3">
        <input type="text" name="username" class="form-control" placeholder="Username" autofocus>
        <button class="btn btn-success" name="action" value="add" type="submit">
          <i class="bi bi-plus-circle"></i> Add User
        </button>
      </div>
      {% if messages %}
        <div class="alert alert-danger" role="alert">
          {{ messages }}
        </div>
      {% endif %}
    </form>

    <h3>Existing Users</h3>
    {% if users_show %}
    <ul class="list-group">
      {% for user in users_show %}
      <li class="list-group-item d-flex justify-content-between align-items-center">
        {{ user }}
        <form method="POST" style="margin:0;">
          <input type="hidden" name="username" value="{{ user }}">
          <button type="submit" class="btn btn-danger btn-sm" name="action" value="remove" onclick="return confirm('Remove user {{ user }}? This will also remove their pages!');">
            <i class="bi bi-trash"></i> Remove
          </button>
        </form>
      </li>
      {% endfor %}
    </ul>
    {% else %}
    <p>No users found.</p>
    {% endif %}
    <a href="{{ url_for('index', space=super_user) }}" class="btn btn-secondary mt-3">
      <i class="bi bi-arrow-left"></i> Back to Wiki
    </a>
    '''
    body = render_template_string(ADMIN_USERS_BODY, messages=messages, users_show=users_show)
    return render_template_string(BASE_HTML, title='User Management', body=body,
                                  current_space=session.get('username'), username=session.get('username'),
                                  display_username='Super User', all_users=[SUPER_USER]+users_list,
                                  super_user=SUPER_USER)

# Helper to check permissions in templates (Jinja can't call normal python functions with multiple args directly)
@app.template_global()
def user_can_edit(username, page_user):
    if not username:
        return False
    if username == SUPER_USER:
        return True
    return username == page_user

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

