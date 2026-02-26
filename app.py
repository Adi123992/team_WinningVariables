from flask import Flask, render_template, request
from price_model import predict_price
from spoilage_model import calculate_spoilage
from explainability import generate_explanation

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/input')
def input_form():
    return render_template('input_form.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    crop = request.form['crop']
    location = request.form['location']
    storage = request.form['storage']
    transit = int(request.form['transit'])

    price = predict_price(crop)
    spoilage = calculate_spoilage(storage, transit)
    explanation = generate_explanation(crop, price, spoilage)

    return render_template('result.html',
                           price=price,
                           spoilage=spoilage,
                           explanation=explanation)

if __name__ == '__main__':
    app.run(debug=True)
