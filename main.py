import boto3
import dash
from dash.dependencies import Input, Output, State
from dash_extensions import Download
from dash_extensions.snippets import send_data_frame
import dash_bootstrap_components as dbc
import dash_html_components as html
import dash_core_components as dcc
from os import getenv
import pandas as pd

from flask_sqlalchemy import SQLAlchemy
from flask import Flask

server = Flask(__name__)
app = dash.Dash(__name__, server=server, external_stylesheets=[dbc.themes.SLATE],
                suppress_callback_exceptions=True)
app.server.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.server.config["SQLALCHEMY_DATABASE_URI"] = 'postgres://umzruzajcpnkum:786ca2f41656de2b76b4168aa6b228b8ab8f282d5fbc\
d615586636e9f89942fe@ec2-52-22-238-188.compute-1.amazonaws.com:5432/dataut4ho9h54r'

db = SQLAlchemy(app.server)


class Results(db.Model):
    __tablename__ = 'labeling-results'

    Image_name = db.Column('Image File Name', db.String(40), nullable=False, primary_key=True)
    Class_name = db.Column('Class', db.String(40), nullable=False)

    def __init__(self, image_name, class_name):
        self.Image_name = image_name
        self.Class_name = class_name


# ----------------------------------------------------------------------------------------------
boto_kwargs = {
    "aws_access_key_id": getenv("AWS_ACCESS_KEY_ID"),
    "aws_secret_access_key": getenv("AWS_SECRET_ACCESS_KEY"),
    "region_name": getenv("AWS_REGION"),
}
s3_client = boto3.Session(**boto_kwargs).client("s3")
s3_resource = boto3.resource('s3')
bucket_name = 'eye-fundi-images-bucket'
my_bucket = s3_resource.Bucket(bucket_name)
images = []

for file in my_bucket.objects.all():
    params = {'Bucket': bucket_name, 'Key': file.key}
    url = s3_client.generate_presigned_url('get_object', params, ExpiresIn=3600)
    images.append({'Bucket': bucket_name, 'Key': file.key, 'ImgURL': url})

# ----------------------------------------------------------------------------------------------
df_table_content = pd.DataFrame(
    {
        "Image File Name": [],
        "Class": [],
    }
)
current_img_index = 0
progress_percentage = 0

image_related_cards = dbc.CardGroup(
    [
        dbc.Card(
            [
                dbc.CardImg(top=True, id="eye-image",
                            title="Image by Kevin Dinkel", alt='Learn Dash Bootstrap Card Component',
                            style={"height": "25rem"}),
                dbc.CardBody(
                    [
                        html.H5(id='name-image', className="card-title"),
                        dbc.Progress(id='progress', color="success")
                    ]
                )],
            outline=False,
            style={"height": "30rem"}
        ),
        dbc.Card(
            dbc.CardBody(
                [
                    html.H4("Click on the diagnosis buttons below to label the show image and display the next one:",
                            className="card-title"),
                    dbc.ListGroup(
                        [
                            dbc.Button("Healthy", color="primary", id='Healthy', n_clicks=0),
                            dbc.Button("Mild", color="secondary", id='Mild', n_clicks=0),
                            dbc.Button("Moderate", color="warning", id='Moderate', n_clicks=0),
                            dbc.Button("Severe", color="danger", id='Severe', n_clicks=0),
                            dbc.Button("Proliferative", color="info", id='Proliferative', n_clicks=0),
                        ]
                    ),
                    # for notification when no more images available
                    html.Div(id='noImages_placeholder', children=[]),
                ]
            ),
            outline=False,
            style={"height": "30rem"}
        )
    ]
)

table_card = dbc.Card(
    [
        dbc.CardBody([
            html.Div(id='placeholder', children=[]),

            # for notification when saving to excel
            html.Div(id='excel_notification_placeholder', children=[]),
            dcc.Store(id="excel_notification_store", data=0),
            dcc.Interval(id='excel_notification_interval', interval=1000),
            Download(id="download"),
            # for notification when saving to database
            html.Div(id='db_notification_placeholder', children=[]),
            dcc.Store(id="db_notification_store", data=0),
            dcc.Interval(id='db_notification_interval', interval=1000),

            dbc.Button("Export Table to Excel", id='excel_btn', color="primary", className="mr-1", n_clicks=0),
            dbc.Button("Submit Table", id='submit_btn', color="primary", className="mr-1", n_clicks=0),
        ]),
    ]
)

app.layout = html.Div([
    image_related_cards,
    table_card,
])


@app.callback(
    [Output('placeholder', 'children'),
     Output('eye-image', 'src'),
     Output('name-image', 'children'),
     Output("progress", "value"),
     Output("progress", "children"),
     Output('noImages_placeholder', 'children')],
    [Input('Healthy', 'n_clicks'),
     Input('Mild', 'n_clicks'),
     Input('Moderate', 'n_clicks'),
     Input('Severe', 'n_clicks'),
     Input('Proliferative', 'n_clicks')]
)
def label_image(Healthy_btn, Mild_btn, Moderate_btn, Severe_btn, Proliferative_btn):
    global df_table_content, current_img_index, progress_percentage
    changed_id = [p['prop_id'] for p in dash.callback_context.triggered][0]
    class_name = None
    noImages_placeholder = ''
    if 'Healthy' in changed_id:
        class_name = 'Healthy'
    elif 'Mild' in changed_id:
        class_name = 'Mild'
    elif 'Moderate' in changed_id:
        class_name = 'Moderate'
    elif 'Severe' in changed_id:
        class_name = 'Severe'
    elif 'Proliferative' in changed_id:
        class_name = 'Proliferative'

    if class_name:
        if current_img_index < len(images) and len(df_table_content) < len(images):
            df_table_content = df_table_content.append({'Image File Name': images[current_img_index]['Key'],
                                                        'Class': class_name}, ignore_index=True)
            labeled_count = current_img_index + 1
            total_count = len(images)
            progress = labeled_count / total_count
            progress_percentage = int(progress * 100)
            # to display next image
            if len(df_table_content) < len(images):
                current_img_index += 1
        else:
            current_img_index = -1
            noImages_placeholder = html.Plaintext("No more Images to Label.",
                                                  style={'color': 'red', 'font-weight': 'bold', 'font-size': 'large'})

    return dbc.Table.from_dataframe(df_table_content, bordered=True, responsive=True, ), images[current_img_index][
        'ImgURL'], \
           images[current_img_index]['Key'], progress_percentage, f"{progress_percentage} %", noImages_placeholder


@app.callback(
    [Output("download", "data"),
     Output('excel_notification_placeholder', 'children'),
     Output("excel_notification_store", "data")],
    [Input('excel_btn', 'n_clicks'),
     Input("excel_notification_interval", "n_intervals")],
    [State('excel_notification_store', 'data')]
)
def save_to_csv(n_clicks, n_intervals, sec):
    no_notification = html.Plaintext("", style={'margin': "0px"})
    notification_text = html.Plaintext("The Shown Table Data has been saved to the excel sheet.",
                                       style={'color': 'green', 'font-weight': 'bold', 'font-size': 'large'})
    input_triggered = dash.callback_context.triggered[0]["prop_id"].split(".")[0]
    if input_triggered == "excel_btn" and n_clicks:
        sec = 10
        return send_data_frame(df_table_content.to_csv, filename="Labeled_Eye_Images.csv"), notification_text, sec
    elif input_triggered == 'excel_notification_interval' and sec > 0:
        sec = sec - 1
        if sec > 0:
            return None, notification_text, sec
        else:
            return None, no_notification, sec
    elif sec == 0:
        return None, no_notification, sec


@app.callback(
    [Output('db_notification_placeholder', 'children'),
     Output("db_notification_store", "data")],
    [Input('submit_btn', 'n_clicks'),
     Input("db_notification_interval", "n_intervals")],
    [State('db_notification_store', 'data')]
)
def save_to_db(n_clicks, n_intervals, sec):
    no_notification = html.Plaintext("", style={'margin': "0px"})
    notification_text = html.Plaintext("The Shown Table Data has been saved to the database.",
                                       style={'color': 'green', 'font-weight': 'bold', 'font-size': 'large'})
    input_triggered = dash.callback_context.triggered[0]["prop_id"].split(".")[0]

    if input_triggered == 'submit_btn':
        sec = 10
        df_table_content.to_sql('labeling-results', con=db.engine, if_exists='replace', index_label=False)
        return notification_text, sec
    elif input_triggered == 'db_notification_interval' and sec > 0:
        sec = sec - 1
        if sec > 0:
            return notification_text, sec
        else:
            return no_notification, sec
    elif sec == 0:
        return no_notification, sec


if __name__ == '__main__':
    app.run_server(debug=True)
