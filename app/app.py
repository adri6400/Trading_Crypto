import streamlit as st
from crypto import test_crypto as crypto


st.title("Application de Trading avec Streamlit")


usdt_balance = crypto.get_usdt_balance()
st.write(f"Solde USDT: {usdt_balance}")