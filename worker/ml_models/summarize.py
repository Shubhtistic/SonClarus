import google.generativeai as genai
import os


def run_summarization(full_transcript_text: str) -> str:
    if not full_transcript_text.strip():
        raise Exception("No transcript content available to summarize.")

    # Retrieve the API key from environment variables
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is missing from env file/config file")
        raise Exception("Error: API Key missing")

    try:
        genai.configure(api_key=api_key)

        # initialize gemini 1.5 flash
        model = genai.GenerativeModel("gemini-2.5-flash")

        # system prompt
        prompt = f"""
        Below is a transcript of an audio conversation. 
        Please provide a professional, single-paragraph synopsis (approx. 100-150 words).
        Identify the main participants, the primary topics discussed, and the final 
        resolution or conclusion of the talk.
        
        Write it in a clean, descriptive style. Do not use bullet points.
        
        TRANSCRIPT:
        {full_transcript_text}
        """

        # Send the request
        response = model.generate_content(prompt)

        if response and response.text:
            return response.text.strip()
        else:
            raise Exception("Summarization returned an empty response.")

    except Exception as e:
        raise Exception(f"Summarize API Failed: {str(e)}")
