from flask import Flask, request, jsonify
import ssl

app = Flask(__name__)

# Dummy database (replace with a real database in production)
user_database = {
    "john.doe@example.com": "John Doe",
    "jane.smith@example.com": "Jane Smith",
    "alice.wonderland@example.com": "Alice Wonderland",
}

@app.route('/user', methods=['GET'])
def get_user_name():
    """Retrieves a user's name based on their email."""
    email = request.args.get('email')

    if not email:
        return jsonify({"error": "Email parameter is required"}), 400

    if email in user_database:
        return jsonify({"name": user_database[email]})
    else:
        return jsonify({"error": "User not found"}), 404

if __name__ == '__main__':
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # Replace with your actual certificate and key files
    context.load_cert_chain('server.crt', 'server.key')
    # Require client certificates
    context.verify_mode = ssl.CERT_REQUIRED
    #load the client CA
    context.load_verify_locations('client_ca.crt')

    app.run(host='0.0.0.0', port=5000, ssl_context=context, debug=True)