import re
import os
import pyreportgen.style as style
import pyreportgen.layout as layout
import pyreportgen.helpers as helpers
import pyreportgen.statistic as statistic
from pyreportgen.base import Component, _DATA_DIR
import uuid
from email import encoders
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib, ssl
import os

if not (_DATA_DIR in os.listdir()):
    os.makedirs(_DATA_DIR, exist_ok=True)


_RE_COMBINE_WHITESPACE = re.compile(r"\s+")



class Report(Component):
    def __init__(self, children:list[Component]=[], style:str=style.STYLE_NORMAL):
        super().__init__()
        self.children = children
        self.style = style

    def render(self) -> str:
        html = ""
        for i in self.children:
            html += i.render()
        html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>{self.style}</style>
                <title>Report</title>
            </head>
            <body>
                <main class="Main">
                    {html}
                </main>
            </body>
        """

        return _RE_COMBINE_WHITESPACE.sub(" ", html).strip()
    
    def pdf(self, path:str, html:str=""):
        import pdfkit 
        if html == "":
            html = self.render()

        with open(_DATA_DIR+'/out.html', 'w', encoding="UTF-8") as f:
            f.write(html)

        pdfkit.from_file(_DATA_DIR+'/out.html', path, options={"--enable-local-file-access":None, "--print-media-type":None})
    
    def email(self, user:str, password:str, subject:str, sender:str, recipient:str, smtp_server:str, context=ssl.create_default_context(), include_pdf=False, pdfname:str="Report"):
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = recipient


        html = self.render()

        filenames = []

        image_lookup = {}

        # Get image tags
        for img in re.findall(r"<img [^>]*>", html):
            # Get the content of the src attribute.
            path = re.findall(r"(?<=src=')[^']*(?=')",img)[0]
            image_lookup[path] = str(uuid.uuid4()) 
            html = html.replace(path, f"cid:{image_lookup[path]}")
            filenames.append(path)



        # Turn these into plain/html MIMEText objects
        html_message = MIMEText(html, "html")

        # Add HTML/plain-text parts to MIMEMultipart message
        # The email client will try to render the last part first
        message.attach(html_message)

        for i in filenames:
            # This example assumes the image is in the current directory
            prefix = ""
            if not ((i.startswith("/")) or (i.startswith("*:\\"))):
                prefix = f"{_DATA_DIR}/"
            fp = open(f"{prefix}{i}", 'rb')
            msgImage = MIMEImage(fp.read())
            fp.close()

            # Define the image's ID as referenced above
            msgImage.add_header('Content-ID', f'<{image_lookup[i]}>')
            message.attach(msgImage)

        
        if include_pdf:

            # Open PDF file in binary mode
            self.pdf(f"{_DATA_DIR}/tmp.pdf")
            with open(f"{_DATA_DIR}/tmp.pdf", "rb") as attachment:
                # Add file as application/octet-stream
                # Email client can usually download this automatically as attachment
                pdf = MIMEBase("application", "octet-stream")
                pdf.set_payload(attachment.read())

            # Encode file in ASCII characters to send by email    
            encoders.encode_base64(pdf)

            # Add header as key/value pair to attachment part
            pdf.add_header(
                "Content-Disposition",
                f"attachment; filename={pdfname}.pdf",
            )



            # Add attachment to message and convert message to string
            message.attach(pdf)

        with smtplib.SMTP_SSL(smtp_server, 465, context=context) as server:
            server.login(user, password)
            server.sendmail(sender, recipient, message.as_string())
    
class Html(Component):
    def __init__(self, html:str):
        super().__init__()
        self.html = html
    def render(self) -> str:
        return self.html

class Text(Component):
    element = "p"

    def __init__(self, text:str, center=False):
        super().__init__()
        self.text = text
        self.center = center
    
    def render(self) -> str:
        classlist = ""
        if self.center:
            classlist += "CenterText "

        return helpers.tagwrap(self.text, self.element, classList=classlist)

class Header(Text):
    def __init__(self, text: str, center=True, heading=1):
        super().__init__(text, center)
        self.element = "h"+str(helpers.clamp(heading, 1, 6))
    
    def render(self) -> str:
        return super().render()

class Image(Component):
    def __init__(self, src: str):
        super().__init__()
        self.src: str = src
    
    def render(self) -> str:
        localizer = "../"
        if self.src.startswith("/"):
            localizer = ""
        return helpers.tagwrap("", "img", "Image", f"src='{localizer}{self.src}'", close=False)
