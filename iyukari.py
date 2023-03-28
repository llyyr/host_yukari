import os
import hashlib
from magic import Magic
from mimetypes import guess_extension
from flask import Flask, request, send_from_directory, make_response, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fileuploads.db'
app.config['URL_ALPHABET'] = 'UrdSo4Aw9UMFfJQg7eUukVzUo2Ve2aQy4mfRzVRCFEPpt5sTTZyCCUjYk223LExd'


class UrlEncoder(object):
    def __init__(self,alphabet, min_length):
        self.alphabet = alphabet
        self.min_length = min_length

    def enbase(self, x):
        n = len(self.alphabet)
        str = ""
        while x > 0:
            str = (self.alphabet[int(x % n)]) + str
            x = int(x // n)
        padding = self.alphabet[0] * (self.min_length - len(str))
        return '%s%s' % (padding, str)

    def debase(self, x):
        n = len(self.alphabet)
        result = 0
        for i, c in enumerate(reversed(x)):
            result += self.alphabet.index(c) * (n ** i)
        return result

su = UrlEncoder(alphabet=app.config["URL_ALPHABET"], min_length=1)

db = SQLAlchemy(app)

class Upload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.UnicodeText)
    sha256 = db.Column(db.UnicodeText)
    ext = db.Column(db.UnicodeText)
    
    def __init__(self, filename, sha256, ext):
        self.filename = filename
        self.sha256 = sha256
        self.ext = ext
    
    def getname(self):
        return u"{0}{1}".format(su.enbase(self.id), self.ext)

    def store(file):
        name, ext = os.path.splitext(file.filename)
        data = file.read()
        
        def get_mime():
            if not file.content_type or not "/" in file.content_type or file.content_type == "application/octet-stream":
                mime = Magic(mime=True, mime_encoding=False).from_buffer(data)
            else:
                mime = file.content_type
            if len(mime) > 128:
                abort(400)

            if mime.startswith("text/") and not "charset" in mime:
                mime += "; charset=utf-8"
            
            return mime
        
        if not ext:
            ext = guess_extension(get_mime().split(";")[0])

        sha256 = hashlib.sha256(data).hexdigest()
        f = Upload.query.filter_by(sha256=sha256).first()
        if f:
            return f
        else:
            filename = sha256 + ext
            file.seek(0)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            upload = Upload(filename=name, sha256=sha256, ext=ext)
            db.session.add(upload)
            db.session.commit()
            return upload

@app.before_first_request
def create_database():
    db.create_all()

@app.route('/')
def index():
    return 'yukariin\n'

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file part\n'
    file = request.files['file']
    if file.filename == '':
        return 'No selected file\n'
    if file:
        upload = Upload.store(file)
        url = url_for('serve_file', path=upload.getname(), _external=True)
        return f'{url}\n'
    return 'Error uploading file\n'

@app.route('/<path:path>')
def serve_file(path):
    filename, *action = path.split('/')
    name, ext = os.path.splitext(filename)
    id = su.debase(name)
    upload = Upload.query.filter_by(id=id).first()
    if upload is None:
        return 'File not found\n'
    sha256 = upload.sha256
    ext = upload.ext
    path = os.path.join(app.config['UPLOAD_FOLDER'], sha256 + ext)
    response = make_response(send_from_directory(app.config['UPLOAD_FOLDER'], sha256 + ext))
    disposition = f'inline; '
    if action:
        disposition = f'attachment; '
    disposition += f'filename="{upload.filename}";'
    response.headers['Content-Disposition'] = disposition
    return response

@app.route('/delete/<path>')
def delete_file(path):
    name, ext = os.path.splitext(path)
    id = su.debase(name)
    upload = Upload.query.filter_by(id=id).first()
    if upload is None:
        return 'File not found\n'
    sha256 = upload.sha256
    ext = upload.ext
    path = os.path.join(app.config['UPLOAD_FOLDER'], sha256 + ext)
    db.session.delete(upload)
    db.session.commit()
    os.remove(path)
    return f'File {upload.filename} has been deleted\n'

@app.route('/favicon.ico')
def favicon():                                     
    return app.send_static_file('favicon.ico')

if __name__ == '__main__':
    app.run(debug=False)

