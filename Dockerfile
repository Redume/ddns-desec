FROM python:3.14-alpine

WORKDIR /

COPY ./requirements.txt .

RUN pip3 install --no-cache-dir --upgrade -r ./requirements.txt

COPY ./ /

CMD ["python", "main.py"]