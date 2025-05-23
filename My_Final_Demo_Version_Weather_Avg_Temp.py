from dotenv import load_dotenv
load_dotenv()
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from openai import OpenAI
import os
import re
import requests

st.set_page_config(page_title="AI Energy Assistant", layout="wide")
st.title("⚡ AI-Enabled Energy Assistant for Customers")

st.header(f"Welcome back 👋")

# Upload data files
st.sidebar.header("📂 Upload Data Files")
energy_file = st.sidebar.file_uploader("Upload Energy Consumption File", type="csv")
billing_file = st.sidebar.file_uploader("Upload Billing History File", type="csv")
payment_file = st.sidebar.file_uploader("Upload Payments File", type="csv")
weather_file = st.sidebar.file_uploader("Upload Weather File", type="csv")
tariff_file = st.sidebar.file_uploader("Upload Tariff Plans File", type="csv")

# Function to fetch weather forecast from WeatherAPI (requires free API key from weatherapi.com)
def get_weather_forecast(city, api_key):
    from datetime import timedelta
    import random

    try:
        url = f"http://api.weatherapi.com/v1/forecast.json?q={city}&days=30&key={api_key}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()["forecast"]["forecastday"]
    except:
        pass

    base_date = datetime.today()
    conditions = ["Sunny", "Partly cloudy", "Cloudy", "Rain showers", "Hot", "Humid", "Thunderstorms"]
    return [
        {
            "date": (base_date + timedelta(days=i)).strftime("%Y-%m-%d"),
            "day": {
                "avgtemp_c": random.randint(28, 38),
                "condition": {"text": random.choice(conditions)}
            }
        }
        for i in range(15)
    ]

data_loaded = False
if energy_file and billing_file and payment_file and weather_file and tariff_file:
    df_energy = pd.read_csv(energy_file)
    df_billing = pd.read_csv(billing_file)
    df_payments = pd.read_csv(payment_file)
    df_weather = pd.read_csv(weather_file)
    df_tariffs = pd.read_csv(tariff_file)

    if "Tariff_Rate_Slab" in df_billing.columns:
        df_billing["Tariff_Rate_Slab"] = df_billing["Tariff_Rate_Slab"].astype(str).str.replace("₹", "£")


    if "Bill_Amount" not in df_billing.columns:
        # Try to guess the bill amount column
        possible_names = ["Amount", "Total", "Total_Bill", "Billing_Amount", "Bill"]
        for name in possible_names:
            if name in df_billing.columns:
                df_billing.rename(columns={name: "Bill_Amount"}, inplace=True)
                break

    data_loaded = True
    st.success("✅ All data files uploaded successfully.")

if data_loaded:
    selected_customer = df_energy["Customer_ID"].iloc[0]
    st.markdown(f"You're viewing insights for **Customer ID: `{selected_customer}`**")

    st.header("📊 My Energy Usage")
    df_energy["Customer_ID"] = df_energy["Customer_ID"].str.strip()
    cust_data = df_energy[df_energy["Customer_ID"] == selected_customer].copy()
    cust_data["Timestamp"] = pd.to_datetime(cust_data["Timestamp"], errors="coerce")
    cust_data = cust_data.sort_values("Timestamp")

    if "Consumption_KWh" not in cust_data.columns:
        cust_data.rename(columns={"Consumption_kWh": "Consumption_KWh"}, inplace=True)

    fig = px.line(cust_data, x="Timestamp", y="Consumption_KWh", title=f"Hourly Consumption for {selected_customer}")
    st.plotly_chart(fig, use_container_width=True)

    st.header("💡 Smart Tips to Reduce My Bill")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    try:
        recent_data = cust_data.resample('D', on='Timestamp')['Consumption_KWh'].sum().tail(7).reset_index()
        usage_series = "\n".join(
            f"{row['Timestamp'].date()}: {row['Consumption_KWh']:.2f} kWh" for _, row in recent_data.iterrows()
        )
        max_usage_day = recent_data.loc[recent_data["Consumption_KWh"].idxmax()]
        min_usage_day = recent_data.loc[recent_data["Consumption_KWh"].idxmin()]
        high_low_note = (
            f"My highest usage was on {max_usage_day['Timestamp'].date()} with {max_usage_day['Consumption_KWh']:.2f} kWh.\n"
            f"My lowest usage was on {min_usage_day['Timestamp'].date()} with {min_usage_day['Consumption_KWh']:.2f} kWh."
        )

        df_weather["Date"] = pd.to_datetime(df_weather["Date"], errors="coerce")
        recent_weather = df_weather.tail(7)
        weather_note = ""
        if not recent_weather.empty:
            avg_temp = recent_weather["Temperature_C"].mean()
            avg_humidity = recent_weather["Humidity_%"].mean()
            weather_note = f"\nYour area's average temperature was {avg_temp:.1f}°C and humidity {avg_humidity:.1f}%."

        payment_note = ""
        if "Payment_Status" in df_payments.columns:
            failed = df_payments[(df_payments["Customer_ID"] == selected_customer) & (df_payments["Payment_Status"] == "Failed")]
            if not failed.empty:
                payment_note = "\nNote: You have missed or failed recent payments."

        tariff_note = ""
        if "Tariff_Rate_Slab" in df_billing.columns:
            tariff_data = df_billing[df_billing["Customer_ID"] == selected_customer]
            if not tariff_data.empty:
                slab = tariff_data["Tariff_Rate_Slab"].dropna().iloc[0]
                tariff_note = f"\nYou are currently billed under this tariff slab: {slab}."

        tip_prompt = (
            f"You are my personal energy assistant.\n"
            f"Here is my energy usage for the past 7 days:\n{usage_series}\n\n"
            f"{high_low_note}\n"
            f"{weather_note}{payment_note}{tariff_note}\n\n"
            f"Based on this, give me 3 friendly and practical suggestions to reduce my electricity bill.\n"
            f"Highlight what I can do differently on high-usage days, how to better manage appliance schedules, and how my current tariff impacts savings."
        )

        if st.button("Show My Energy-Saving Suggestions"):
            with st.spinner("Generating personalized tips using OpenAI..."):
                tip_response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": tip_prompt}]
                )
                tips = tip_response.choices[0].message.content
                st.text_area("🧠 AI-Generated Cost Saving Tips", value=tips, height=250)
    except Exception as tip_err:
        st.warning("⚠️ Could not generate GenAI tips. Showing default tip.")
        st.info("Try using appliances during off-peak hours and unplug unused devices to reduce phantom load.")

    
    st.header("🌦️ How Weather Affects My Usage")
    try:
        # Group weather data by date to get daily average temperature and humidity
        df_weather['Date'] = pd.to_datetime(df_weather['Date'], errors='coerce')
        # Prepare daily energy data from customer consumption
        daily_energy = cust_data.resample('D', on='Timestamp')['Consumption_KWh'].sum().reset_index()
        daily_weather = df_weather.groupby(df_weather['Date'].dt.date).agg({
            'Temperature_C': 'mean',
            'Humidity_%': 'mean'
        }).reset_index().rename(columns={'Date': 'Timestamp'})

        # Prepare daily energy data
        daily_energy['Timestamp'] = daily_energy['Timestamp'].dt.date
        merged = pd.merge(daily_energy, daily_weather, on='Timestamp')
        df_weather["Date"] = pd.to_datetime(df_weather["Date"], errors="coerce")

        if "Temperature_C" in merged.columns and "Consumption_KWh" in merged.columns:
            fig_weather = px.line(
                merged,
                x="Timestamp",
                y=["Consumption_KWh", "Temperature_C"],
                labels={"value": "Value", "variable": "Metric"},
                title="Daily Energy Consumption vs Temperature Trend"
            )
            st.plotly_chart(fig_weather, use_container_width=True)

            # Add AI insight section
            temp_consumption_series = "\n".join(
                f"{row['Timestamp']}: {row['Temperature_C']}°C, {row['Consumption_KWh']:.2f} kWh"
                for _, row in merged.iterrows()
            )

            temp_prompt = (
                f"You are my personal energy assistant.\n"
                f"Here is my recent daily temperature and energy usage:\n"
                f"{temp_consumption_series}\n\n"
                f"Based on this, give me 2–3 insights about how the weather affects my energy consumption.\n"
                f"Include friendly, actionable tips I can follow during hot or cold days to save energy and stay comfortable."
            )

            with st.spinner("Analyzing how weather impacts your usage..."):
                temp_response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": temp_prompt}]
                )
                st.text_area("🧠 AI Insight on Weather vs Usage", temp_response.choices[0].message.content, height=220)
        else:
            st.warning("Missing temperature or consumption data for the graph.")
    except Exception as e:
        st.error(f"Error generating temperature vs consumption chart: {e}")


    st.header("🔮 Forecast My Next Month's Usage (with Weather)")
    try:
        cust_data_daily = cust_data.resample('D', on='Timestamp')['Consumption_KWh'].sum().reset_index()
        daily_series = ", ".join([f"{row['Timestamp'].date()}: {row['Consumption_KWh']:.2f} kWh" for _, row in cust_data_daily.tail(30).iterrows()])

        forecast_weather = get_weather_forecast("Delhi", os.getenv("WEATHER_API_KEY"))
        weather_summary = "\n".join([
            f"{w['date']}: {w['day']['avgtemp_c']}°C, {w['day']['condition']['text']}"
            for w in forecast_weather
        ]) if forecast_weather else "No forecast data available."

        forecast_prompt = (
            f"You are my AI assistant. Here is my energy usage over the last 30 days:\n"
            f"{daily_series}\n\n"
            f"Here is the weather forecast for the next 15 days:\n{weather_summary}\n\n"
            f"Please forecast how much energy I’ll likely use over the next 15 days. For each day, mention the forecasted temperature and weather condition followed by the predicted energy consumption.\n"
            f"Format: Date - Weather - Predicted Consumption (kWh)"
        )

        if st.button("Forecast My Weather-Aware Usage"):
            with st.spinner("Requesting forecast from OpenAI..."):
                response = OpenAI(api_key=os.getenv("OPENAI_API_KEY")).chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": forecast_prompt}]
                )
                forecast_text = response.choices[0].message.content
                st.text_area("📋 My Energy Usage Forecast (Weather-Aware)", value=forecast_text, height=350)

                forecast_lines = re.findall(r"(\d{4}-\d{2}-\d{2})\s*-\s*([\w\s]+),?\s*(\d+\.\d+)\s*kWh", forecast_text)
                if forecast_lines:
                    forecast_df = pd.DataFrame(forecast_lines, columns=["Date", "Weather", "Predicted_Consumption_KWh"])
                    forecast_df["Date"] = pd.to_datetime(forecast_df["Date"])
                    forecast_df["Predicted_Consumption_KWh"] = forecast_df["Predicted_Consumption_KWh"].astype(float)

                    fig_forecast = px.line(forecast_df, x="Timestamp", y="Predicted_Consumption_KWh", color_discrete_sequence=["green"], title="Forecasted Daily Consumption (Next 15 Days)")
                    st.plotly_chart(fig_forecast, use_container_width=True)
                    st.dataframe(forecast_df)

    except Exception as e:
        st.error(f"Forecasting error: {e}")

    
    st.header("💬 Ask Me Anything About Your Energy Data")

    user_query = st.text_input("What would you like to know?", placeholder="E.g., Why was my usage high last week?")

    if st.button("Ask My Assistant"):
        with st.spinner("Thinking..."):
            summary_parts = []

            try:
                daily_usage = cust_data.resample('D', on='Timestamp')['Consumption_KWh'].sum().tail(7)
                usage_summary = "\n".join([f"{idx.date()}: {val:.2f} kWh" for idx, val in daily_usage.items()])
                summary_parts.append(f"My past 7 days of energy usage:\n{usage_summary}")
            except:
                pass

            try:
                bills = df_billing[df_billing["Customer_ID"] == selected_customer].tail(3)
                bill_summary = "\n".join([f"{row['Billing_Period']}: £{row['Bill_Amount']}" for _, row in bills.iterrows()])
                summary_parts.append(f"My recent billing history:\n{bill_summary}")
            except:
                pass

            try:
                payments = df_payments[df_payments["Customer_ID"] == selected_customer].tail(3)
                payment_summary = "\n".join([f"{row['Transaction_Date']}: £{row['Amount_Paid']} - {row['Payment_Status']}" for _, row in payments.iterrows()])
                summary_parts.append(f"My payment activity:\n{payment_summary}")
            except:
                pass

            try:
                weather_recent = df_weather.tail(5)
                weather_info = "\n".join([f"{row['Date']}: {row['Temperature_C']}°C" for _, row in weather_recent.iterrows()])
                summary_parts.append(f"Recent temperature data:\n{weather_info}")
            except:
                pass

            query_prompt = (
                "You are an AI assistant helping a utility customer based on their personal energy data.\n\n"
                + "\n\n".join(summary_parts)
                + f"\n\nThe customer asks: {user_query}\n\n"
                "Give a clear and helpful answer."
            )

            try:
                answer = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": query_prompt}]
                )
                st.text_area("🤖 Assistant's Response", value=answer.choices[0].message.content, height=250)
            except Exception as e:
                st.error(f"Query failed: {e}")


    st.header("📄 My Billing History")
    if not df_billing[df_billing["Customer_ID"] == selected_customer].empty:
        billing_display = df_billing[df_billing["Customer_ID"] == selected_customer].copy()
        if "Amount_Paid" in billing_display.columns:
            billing_display = billing_display.drop(columns=["Amount_Paid"])
        st.dataframe(billing_display)

    st.header("💳 My Payment Activity")
    if not df_payments[df_payments["Customer_ID"] == selected_customer].empty:
        st.dataframe(df_payments[df_payments["Customer_ID"] == selected_customer])

    st.header("🎯 Personalized Plan Recommendations")

    # Ensure fallback renaming is reapplied here before checking
    if "Bill_Amount" not in df_billing.columns:
        possible_names = ["Amount", "Total", "Total_Bill", "Billing_Amount", "Bill"]
        for name in possible_names:
            if name in df_billing.columns:
                df_billing.rename(columns={name: "Bill_Amount"}, inplace=True)
                break

    st.text("🛠️ Billing Columns: " + ", ".join(df_billing.columns))
    try:
        if "Bill_Amount" in df_billing.columns:
            recent_bill_avg = df_billing[df_billing["Customer_ID"] == selected_customer]["Bill_Amount"].tail(3).mean()
            failed_payments = df_payments[(df_payments["Customer_ID"] == selected_customer) & (df_payments["Payment_Status"].str.lower() == "failed")]

            tariffs_text = "\n".join([
                f"{row['Tariff_Name']} - {row['Tariff_Type']} - £{row['Rate_Per_Unit']}/unit, Fixed £{row['Fixed_Charge']}"
                for _, row in df_tariffs.iterrows()
            ])

            offer_prompt = (
                f"My recent average monthly bill is £{recent_bill_avg:.2f}.\n"
                f"{'I have missed recent payments.' if not failed_payments.empty else 'My payments are on time.'}\n"
                f"Here are the available tariff options:\n{tariffs_text}\n\n"
                f"Please suggest 2–3 suitable offers, adjustments, or tariff changes based on my payment history and these plans."
            )

            if st.button("🎁 Show Personalized Bill Relief Offers"):
                with st.spinner("Generating plan recommendations..."):
                    offer_response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": offer_prompt}]
                    )
                    st.text_area("🏷️ Plan Suggestions & Offers", offer_response.choices[0].message.content, height=220)
        else:
            st.warning("⚠️ 'Bill_Amount' column is missing from your billing file. Plan recommendations cannot be generated.")
    except Exception as e:
        st.warning(f"Offer generation failed: {e}")
