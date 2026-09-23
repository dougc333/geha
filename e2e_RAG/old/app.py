from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from jsonargparse import CLI
from rag import (
    create_parent_retriever,
    get_ensemble_retriever,
    load_embedding_model,
    load_pdf,
    retrieve_context_reranked,
    create_multi_query_retriever
)




def main(
    file: str = "../data/2306.02707v1.pdf",
):
    

    llm = ChatOpenAI(model_name="gpt-4o")

    docs = load_pdf(files=file)

    embedding_model = load_embedding_model()
    base_retriever = create_parent_retriever(docs, embedding_model, collection_name="test-1")
    retriever = create_multi_query_retriever(base_retriever, llm)

    prompt_template = ChatPromptTemplate.from_template(
        (
            """
            You are an experienced academic researcher. Your job is to extract information from the provided CONTEXT based on the user question.
            Think step by step and only use the information from the CONTEXT that is relevant to the user question. Provide detailed responses.   

            QUESTION: ```{question}```\n
            CONTEXT: ```{context}```\n"""
        )
    )

    chain = prompt_template | llm | StrOutputParser()

    while True:
        query = input("User Input: ")

        if query=="exit":
            break

        context = retrieve_context_reranked(
            query, retriever=retriever, reranker_model="gpt"
        )
        # print(f"Here is the context: {context}")
        text = ""
        for i,chunk in enumerate(context):
            if i <3:
                text = text +"\n"+ chunk
            else:
                break

        print("\n\nLLM Response: ", end="")
        for e in chain.stream({"context": text, "question": query}):
            print(e, end="")
        print("\n\n\n")

        show_sources = False
        if show_sources:

            print("\n\n\n--------------------------------CONTEXT-------------------------------------")

            for i,chunk in enumerate(context):
                print(f"-----------------------------------Chunk: {i}--------------------------------------")
                print(f"Context: {chunk}")



if __name__ == "__main__":

    CLI(main)