
import streamlit as st
from typing import List
from Agent.agent1_module import ProductDetailAgent
from Agent.Agent2 import Agent2

st.set_page_config(page_title="Subsidy Calculator Agent", layout="centered")

st.title("🧮 Subsidy Calculator Agent")
st.markdown("Use this tool to calculate product subsidy discounts for a specific community. Add multiple products dynamically and compute subsidies.")

if "product_inputs" not in st.session_state:
    st.session_state.product_inputs = [""]

def add_product_input():
    st.session_state.product_inputs.append("")

st.header("📝 Input Section")

community_id = st.text_input("Enter Community ID", key="community_id_input")

st.subheader("➕ Add Product Names")
for i, pname in enumerate(st.session_state.product_inputs):
    st.session_state.product_inputs[i] = st.text_input(f"Product Name {i+1}", value=pname, key=f"product_{i}")

st.button("➕ Add Another Product", on_click=add_product_input)

if st.button("Calculate Subsidies"):
    product_inputs = [p.strip() for p in st.session_state.product_inputs if p.strip()]
    
    if not product_inputs or not community_id.strip():
        st.warning("Please enter at least one product and a community ID.")
    else:
        agent1 = ProductDetailAgent()

        for pname in product_inputs:
            st.markdown(f"---\n### 🛠️ Processing for **{pname}**")
            st.info("Agent1 is working...")
            product_state = agent1.extract_product_details(pname)
            st.json(product_state)

            if not product_state.get("subsidy_level"):
                st.error(f"Could not determine subsidy level for {pname}. Skipping.")
                continue

            st.info(f"Agent2 is working for Community ID: `{community_id}`")
            agent2 = Agent2(community_id)
            result = agent2.run(product_state)
            st.json(result)

            st.success(
                f"For product **{result['product_name']}**, subsidy level is **{result['subsidy_level']}** "
                f"in **{result['community_id']}**, and the discount per kg is **${result['discount_per_kg']}**."
            )

st.markdown("---")
st.caption("Built with ❤️ using Streamlit.")