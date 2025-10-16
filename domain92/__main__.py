from PIL import Image
from io import BytesIO
import time
import requests as req
import re
import random
import string
from art import *
import freedns
import sys
import argparse
import pytesseract
import copy
from PIL import ImageFilter
import os
import platform
from importlib.metadata import version
import lolpython
import time
import random_header_generator
import temp_mails
headergen = random_header_generator.HeaderGenerator()
parser = argparse.ArgumentParser(
    description="Automatically creates links for an ip on freedns"
)
parser.add_argument(
    "-v",
    "--version",
    action="version",
    version="domain92 installed with version: " + str(version("domain92")),
    help="show the installed version of this package (domain92)",
)
parser.add_argument("--number", help="number of links to generate", type=int)
parser.add_argument("--ip", help="ip to use", type=str)
parser.add_argument("--webhook", help="webhook url, do none to not ask", type=str)
parser.add_argument(
    "--proxy", help="use if you get ip blocked.", type=str, default="none"
)
parser.add_argument(
    "--use_tor",
    help="use a local tor proxy to avoid ip blocking. See wiki for instructions.",
    action="store_true",
)
parser.add_argument(
    "--silent",
    help="no output other than showing you the captchas",
    action="store_true",
)
parser.add_argument(
    "--outfile", help="output file for the domains", type=str, default="domainlist.txt"
)
parser.add_argument(
    "--type", help="type of record to make, default is A", type=str, default="A"
)
parser.add_argument(
    "--pages",
    help="range of pages to scrape, see wiki for more info (default is first ten)",
    type=str,
)
parser.add_argument(
    "--subdomains",
    help="comma separated list of subdomains to use, default is random",
    type=str,
    default="random",
)
parser.add_argument(
    "--auto",
    help="uses tesseract to automatically solve the captchas. tesseract is now included, and doesn't need to be installed seperately",
    action="store_true",
)
parser.add_argument("--domain_type", help="Force only public or only private domains, `public` or `private`", type=str)
parser.add_argument("--single_tld", help="only create links for a single tld", type=str)
args = parser.parse_args()
ip = args.ip
if not args.silent:
    lolpython.lol_py(text2art("domain92"))
    print("made with <3 by Cbass92")
    time.sleep(1)


def checkprint(input):
    global args
    if not args.silent:
        print(input)


client = freedns.Client()

checkprint("client initialized")


def get_data_path():
    script_dir = os.path.dirname(__file__)
    checkprint("checking os")
    if platform.system() == "Windows":
        filename = os.path.join(script_dir, "data", "windows", "tesseract")
    elif platform.system() == "Linux":
        filename = os.path.join(script_dir, "data", "tesseract-linux")
    else:
        print(
            "Unsupported OS. This could cause errors with captcha solving. Please install tesseract manually."
        )
        return None
    os.environ["TESSDATA_PREFIX"] = os.path.join(script_dir, "data")
    return filename


path = get_data_path()
if path:
    pytesseract.pytesseract.tesseract_cmd = path
    checkprint(f"Using tesseract executable: {path}")
else:
    checkprint("No valid tesseract file for this OS.")

domainlist = []
domainnames = []
checkprint("getting ip list")
iplist = req.get(
    "https://raw.githubusercontent.com/sebastian-92/byod-ip/refs/heads/master/byod.json"
).text
iplist = eval(iplist)


def getpagelist(arg):
    arg = arg.strip()
    if not arg:
        checkprint("Empty page range")
        sys.exit(1)

    pagelist = []
    parts = [p.strip() for p in arg.split(",") if p.strip() != ""]

    for item in parts:
        if "-" in item:
            sublist = item.split("-")
            if len(sublist) == 2:
                try:
                    sp = int(sublist[0])
                    ep = int(sublist[1])
                except ValueError:
                    checkprint("Invalid page number: " + item)
                    sys.exit(1)
                if sp < 1 or sp > ep:
                    checkprint("Invalid page range: " + item)
                    sys.exit(1)
                pagelist.extend(range(sp, ep + 1))
            else:
                checkprint("Invalid page range: " + item)
                sys.exit(1)
        else:
            try:
                p = int(item)
            except ValueError:
                checkprint("Invalid page number: " + item)
                sys.exit(1)
            if p < 1:
                checkprint("Invalid page number: " + item)
                sys.exit(1)
            pagelist.append(p)

    seen = set()
    result = []
    for p in pagelist:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


def getdomains(arg):
    global domainlist, domainnames
    for sp in getpagelist(arg):
        checkprint("getting page " + str(sp))
        html = req.get(
            "https://freedns.afraid.org/domain/registry/?page="
            + str(sp)
            + "&sort=2&q=",
            headers=headergen(),
        ).text
        if args.domain_type == 'private':
            checkprint('parsing for private domains')
            pattern = r"<a href=\/subdomain\/edit\.php\?edit_domain_id=(\d+)>([\w.-]+)<\/a>(.+\..+)<td>private<\/td>"
        elif args.domain_type == 'public':
            checkprint('parsing for public domains')
            pattern = r"<a href=\/subdomain\/edit\.php\?edit_domain_id=(\d+)>([\w.-]+)<\/a>(.+\..+)<td>public<\/td>"
        else:
            checkprint('parsing for both private and public domains')
            pattern = r"<a href=\/subdomain\/edit\.php\?edit_domain_id=(\d+)>([\w.-]+)<\/a>(.+\..+)<td>(public|private)<\/td>"
        matches = re.findall(pattern, html)
        domainnames.extend([match[1] for match in matches])
        domainlist.extend([match[0] for match in matches])


def find_domain_id(domain_name):
    page = 1
    html = req.get(
        "https://freedns.afraid.org/domain/registry/?page="
        + str(page)
        + "&q="
        + domain_name,
        headers=headergen(),
    ).text
    pattern = r"<a href=\/subdomain\/edit\.php\?edit_domain_id=([0-9]+)><font color=red>(?:.+\..+)<\/font><\/a>"
    matches = re.findall(pattern, html)
    if len(matches) > 0:
        checkprint(f"Found domain ID: {matches[0]}")
    else:
        raise Exception("Domain ID not found")
    return matches[0]


hookbool = False
webhook = ""
if args.subdomains != "random":
    checkprint("Subdomains set to:")
    checkprint(args.subdomains.split(","))
checkprint("ready")


def getcaptcha():
    return Image.open(BytesIO(client.get_captcha()))


def denoise(img):
    imgarr = img.load()
    newimg = Image.new("RGB", img.size)
    newimgarr = newimg.load()
    dvs = []
    for y in range(img.height):
        for x in range(img.width):
            r = imgarr[x, y][0]
            g = imgarr[x, y][1]
            b = imgarr[x, y][2]
            if (r, g, b) == (255, 255, 255):
                newimgarr[x, y] = (r, g, b)
            elif ((r + g + b) / 3) == (112):
                newimgarr[x, y] = (255, 255, 255)
                dvs.append((x, y))
            else:
                newimgarr[x, y] = (0, 0, 0)

    backup = copy.deepcopy(newimg)
    backup = backup.load()
    for y in range(img.height):
        for x in range(img.width):
            if newimgarr[x, y] == (255, 255, 255):
                continue
            black_neighbors = 0
            for ny in range(max(0, y - 2), min(img.height, y + 2)):
                for nx in range(max(0, x - 2), min(img.width, x + 2)):
                    if backup[nx, ny] == (0, 0, 0):
                        black_neighbors += 1
            if black_neighbors <= 5:
                newimgarr[x, y] = (255, 255, 255)
    for x, y in dvs:
        black_neighbors = 0
        for ny in range(max(0, y - 2), min(img.height, y + 2)):
            for nx in range(max(0, x - 1), min(img.width, x + 1)):
                if newimgarr[nx, ny] == (0, 0, 0):
                    black_neighbors += 1
            if black_neighbors >= 5:
                newimgarr[x, y] = (0, 0, 0)
            else:
                newimgarr[x, y] = (255, 255, 255)
    width, height = newimg.size
    black_pixels = set()
    for y in range(height):
        for x in range(width):
            if newimgarr[x, y] == (0, 0, 0):
                black_pixels.add((x, y))

    for x, y in list(black_pixels):
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in black_pixels:
                newimgarr[nx, ny] = 0
    backup = copy.deepcopy(newimg)
    backup = backup.load()
    for y in range(img.height):
        for x in range(img.width):
            if newimgarr[x, y] == (255, 255, 255):
                continue
            black_neighbors = 0
            for ny in range(max(0, y - 2), min(img.height, y + 2)):
                for nx in range(max(0, x - 2), min(img.width, x + 2)):
                    if backup[nx, ny] == (0, 0, 0):
                        black_neighbors += 1
            if black_neighbors <= 6:
                newimgarr[x, y] = (255, 255, 255)
    return newimg


def solve(image):
    image = denoise(image)
    text = pytesseract.image_to_string(
        image.filter(ImageFilter.GaussianBlur(1))
        .convert("1")
        .filter(ImageFilter.RankFilter(3, 3)),
        config="-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ --psm 13 -l freednsocr",
    )
    text = text.strip().upper()
    checkprint("captcha solved: " + text)
    if len(text) != 5 and len(text) != 4:
        checkprint("captcha doesn't match correct pattern, trying different captcha")
        text = solve(getcaptcha())
    return text


def generate_random_string(length):
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for i in range(length))


def login():
    while True:
        try:
            checkprint("getting captcha")
            image = getcaptcha()
            if args.auto:
                capcha = solve(image)
                checkprint("captcha solved (hopefully)")
            else:
                checkprint("showing captcha")
                image.show()
                capcha = input("Enter the captcha code: ")
            checkprint("generating email")
            mail = temp_mails.Generator_email()
            print('using mail provider: '+ mail.__class__.__name__ )
            email = mail.email
            checkprint("email address generated email: " + email)
            checkprint("creating account")
            username = generate_random_string(random.randint(8, 13))
            client.create_account(
                capcha,
                generate_random_string(13),
                generate_random_string(13),
                username,
                'pegleg1234',
                email,
            )
            checkprint("activation email sent")
            checkprint("waiting for email")
            text = mail.wait_for_new_email(timeout=30)
            if not text:
                checkprint("no email received, trying again")
                continue
            checkprint("email received, getting content")
            content = str(mail.get_mail_content(mail_id=text["id"]))
            if content:
                checkprint("email content found")
            if text:
                checkprint("email received")
                match = re.search(r'\?([^">]+)"', content)
                if match:
                    checkprint("code found")
                    checkprint("verification code: " + match.group(1))
                    checkprint("activating account")
                    client.activate_account(match.group(1))
                    checkprint("account activated")
                    time.sleep(1)
                    checkprint("attempting login")
                    client.login(email, 'pegleg1234')
                    checkprint("login successful")
                else:
                    checkprint(
                        "no match in email! you should generally never get this."
                    )
                    checkprint("error!")
                    continue
        except KeyboardInterrupt:
            sys.exit()
        except Exception as e:
            checkprint("Got error while creating account: " + repr(e))
            if args.use_tor:
                checkprint("attempting to change tor identity")
                try:
                    from stem import Signal
                    from stem.control import Controller

                    with Controller.from_port(port=9051) as controller:
                        controller.authenticate()
                        controller.signal(Signal.NEWNYM)
                        time.sleep(controller.get_newnym_wait())
                        checkprint("tor identity changed")
                except Exception as e:
                    checkprint("Got error while changing tor identity: " + repr(e))
                    continue
            continue
        else:
            break


def createlinks(number):
    for i in range(number):
        if i % 5 == 0:
            if args.use_tor:
                checkprint("attempting to change tor identity")
                try:
                    from stem import Signal
                    from stem.control import Controller

                    with Controller.from_port(port=9051) as controller:
                        controller.authenticate()
                        controller.signal(Signal.NEWNYM)
                        time.sleep(controller.get_newnym_wait())
                        checkprint("tor identity changed")
                except Exception as e:
                    checkprint("Got error while changing tor identity: " + repr(e))
                    checkprint("Not going to try changing identity again")
                    args.use_tor = False
            login()
        createdomain()


def createdomain():
    while True:
        try:
            image = getcaptcha()
            if args.auto:
                capcha = solve(image)
                checkprint("captcha solved")
            else:
                checkprint("showing captcha")
                image.show()
                capcha = input("Enter the captcha code: ")

            if args.single_tld:
                random_domain_id = non_random_domain_id
            else:
                random_domain_id = random.choice(domainlist)
            if args.subdomains == "random":
                subdomainy = generate_random_string(10)
            else:
                subdomainy = random.choice(args.subdomains.split(","))
            client.create_subdomain(capcha, args.type, subdomainy, random_domain_id, ip)
            tld = args.single_tld or domainnames[domainlist.index(random_domain_id)]
            checkprint("domain created")
            checkprint("link: http://" + subdomainy + "." + tld)
            domainsdb = open(args.outfile, "a")
            domainsdb.write("\nhttp://" + subdomainy + "." + tld)
            domainsdb.close()
            if hookbool:
                checkprint("notifying webhook")
                req.post(
                    webhook,
                    json={
                        "content": "Domain created:\nhttp://"
                        + subdomainy
                        + "."
                        + tld
                        + "\n ip: "
                        + ip
                    },
                )
                checkprint("webhook notified")
        except KeyboardInterrupt:
            # quit
            sys.exit()
        except Exception as e:
            checkprint("Got error while creating domain: " + repr(e))
            continue
        else:
            break


non_random_domain_id = None


def finddomains(pagearg):
    pages = pagearg.split(",")
    for page in pages:
        getdomains(page)


def init():
    global args, ip, iplist, webhook, hookbool, non_random_domain_id
    if not args.ip:
        chosen = chooseFrom(iplist, "Choose an IP to use:")
        match chosen:
            case "custom":
                ip = input("Enter the custom IP: ")
            case _:
                ip = iplist[chosen]
        args.ip = ip  # Assign the chosen/entered IP back to args
    else:
        ip = args.ip  # Ensure ip variable is set even if provided via CLI
    if not args.pages:
        args.pages = (
            input(
                "Enter the page range(s) to scrape (e.g., 15 or 5,8,10-12, default: 10): "
            )
            or "10"
        )

    if not args.webhook:
        match input("Do you want to use a webhook? (y/n) ").lower():
            case "y":
                hookbool = True
                webhook = input("Enter the webhook URL: ")
                args.webhook = webhook  # Assign entered webhook back to args
            case "n":
                hookbool = False
                args.webhook = "none"  # Explicitly set to none if declined
    else:
        if args.webhook.lower() == "none":
            hookbool = False
        else:
            hookbool = True
            webhook = args.webhook  # Ensure webhook variable is set

    if (not args.proxy) and (
        not args.use_tor
    ):  # Only ask if neither proxy nor tor is set
        match input("Do you want to use a proxy? (y/n) ").lower():
            case "y":
                args.proxy = input(
                    "Enter the proxy URL (e.g., http://user:pass@host:port): "
                )
            case "n":
                match input(
                    "Do you want to use Tor (local SOCKS5 proxy on port 9050)? (y/n) "
                ).lower():
                    case "y":
                        args.use_tor = True
                    case "n":
                        pass  # Neither proxy nor Tor selected
    if args.proxy == "none":
        args.proxy == False

    if not args.outfile:
        args.outfile = (
            input(f"Enter the output filename for domains (default: {args.outfile}): ")
            or args.outfile
        )

    if not args.type:
        args.type = (
            input(f"Enter the type of DNS record to create (default: {args.type}): ")
            or args.type
        )

    if not args.pages:
        args.pages = (
            input(
                f"Enter the page range(s) to scrape (e.g., 1-10 or 5,8,10-12, default: {args.pages}): "
            )
        )

    if not args.subdomains:
        match input("Use random subdomains? (y/n) ").lower():
            case "n":
                args.subdomains = input(
                    "Enter comma-separated list of subdomains to use: "
                )
            case "y":
                pass

    if not args.number:
        num_links_input = input("Enter the number of links to create: ")
        try:
            num_links = int(num_links_input)
            args.number = num_links
        except ValueError:
            checkprint("Invalid number entered. Exiting.")
            sys.exit(1)
    if not args.auto:
        match input("Use automatic captcha solving? (y/n) ").lower():
            case "y":
                args.auto = True
            case "n":
                args.auto = False

    if args.use_tor:
        checkprint("using local tor proxy on port 9050")
        proxies = {
            "http": "socks5h://127.0.0.1:9050",
            "https": "socks5h://127.0.0.1:9050",
        }
        client.session.proxies.update(proxies)
        checkprint("tor proxy set")

    if args.proxy != "none":
        checkprint("setting proxy with proxy: " + args.proxy)
        proxies = {"http": args.proxy, "https": args.proxy}
        client.session.proxies.update(proxies)
        checkprint("proxy set")
    if args.single_tld:
        checkprint("Using single domain mode")
        checkprint("Finding domain ID for: " + args.single_tld)
        non_random_domain_id = find_domain_id(args.single_tld)
        checkprint(f"Using single domain ID: {non_random_domain_id}")
    else:
        finddomains(args.pages)

    if args.number:
        createlinks(args.number)


def chooseFrom(dictionary, message):
    checkprint(message)
    for i, key in enumerate(dictionary.keys()):
        checkprint(f"{i+1}. {key}")
    choice = int(input("Choose an option by number: "))
    return list(dictionary.keys())[choice - 1]


if __name__ == "__main__":
    init()
