from flask import Flask, request, jsonify
from flask_cors import CORS
from gevent import monkey

monkey.patch_all()

from NERD import nerd

app = Flask(__name__)

app.config['JSON_AS_ASCII'] = False


@app.route('/', methods=['GET'])
def greek_ner():
    t = request.args
    if 'text' in t:
        return jsonify(nerd(t))
    else:
        result = nerd(t)
        r = []
        for x in result:
            r.append({x['matched_string']: x['wiki_page']})
        return jsonify(r)


if __name__ == "__main__":
    app.run(port=20000, host='0.0.0.0')
