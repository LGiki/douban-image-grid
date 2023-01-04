import math
import requests
import argparse
from PIL import Image
import logging
from bs4 import BeautifulSoup
import datetime
import os


def init_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s: %(message)s'
    )


def mkdir_if_not_exists(folder_path: str):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)


def generate_output_filename(douban_id, mode):
    date = datetime.datetime.today().strftime('%Y%m%d')
    return f'{douban_id}_{mode}_{date}.png'


def get_large_image_url(url: str, mode: str):
    if mode == 'movie':
        return url.replace('s_ratio_poster', 'l_ratio_poster')
    else:
        return url.replace('subject/s', 'subject/l')


def download_images(images_urls: list[str], cache_folder: str, mode: str) -> list[str]:
    image_paths = []
    for image_url in images_urls:
        image_name = image_url.split('/')[-1]
        image_cache_folder = os.path.join(cache_folder, mode)
        mkdir_if_not_exists(image_cache_folder)
        image_path = os.path.join(image_cache_folder, image_name)
        if not os.path.exists(image_path):
            logging.info(f'Downloading {image_url} to {image_path}.')
            response = requests.get(image_url)
            with open(image_path, 'wb') as f:
                f.write(response.content)
        else:
            logging.info(f'{image_name} already exists, skip downloading.')
        image_paths.append(image_path)
    return image_paths


def generate_image_grid(image_paths: list[str], column: int, height: int, width: int, output_path: str):
    if len(image_paths) < column:
        column = len(image_paths)
    row = math.ceil(len(image_paths) / column)
    result_image = Image.new('RGBA', (width * column, height * row), (255, 255, 255, 0))
    for (index, image_path) in enumerate(image_paths):
        image = Image.open(image_path)
        image = image.resize((width, height), Image.LANCZOS)
        result_image.paste(image, (width * (index % column), height * (index // column)))
    result_image.save(output_path)


def get_image_urls(douban_id: str, mode: str, target_year: str, user_agent: str, cookie: str) -> list[str]:
    image_urls = []

    page_index = 0

    request_headers = {
        'User-Agent': user_agent,
    }

    if len(cookie) != 0:
        request_headers['Cookie'] = cookie

    while True:
        url = f'https://{mode}.douban.com/people/{douban_id}/collect?start={page_index}&sort=time&rating=all&filter' \
              f'=all&mode=grid'

        logging.info(f'Process {url}')

        response = requests.get(
            url,
            headers=request_headers
        )

        if response.status_code != 200:
            logging.error(f'Error {response.status_code}: {response.text}')
            logging.info('Please specify a valid cookie and try again.')
            exit(1)

        bs = BeautifulSoup(response.text, features='html.parser')

        if mode == 'book':
            elements = bs.findAll('li', {'class': 'subject-item'})
        else:
            elements = bs.findAll('div', {'class': 'item'})

        is_finished = False

        if elements:
            for element in elements:
                image_url = element.find('a', {'class': 'nbg'}).find('img', recursive=False)['src']
                large_image_url = get_large_image_url(image_url, mode)
                marked_date = element.find('span', {'class': 'date'}).text
                marked_year = int(marked_date.split('-')[0])

                if target_year != 'all':
                    if marked_year > int(target_year):
                        continue
                    elif marked_year < int(target_year):
                        is_finished = True
                        break

                image_urls.append(large_image_url)
        else:
            break

        if is_finished:
            break

        page_index += 15
    return image_urls


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--id',
        type=str,
        required=True,
        help='Your douban user ID.'
    )
    parser.add_argument(
        '--mode',
        type=str,
        choices=['book', 'movie', 'music'],
        default='book',
        help='Generate mode, can be "book", "movie" or "music".'
    )
    parser.add_argument(
        '--year',
        type=str,
        default=datetime.date.today().year,
        help='Target year, default is current year, set to "all" to generate all years.'
    )
    parser.add_argument(
        '--width',
        type=int,
        default=600,
        help='Image width, default is 600.'
    )
    parser.add_argument(
        '--height',
        type=int,
        default=800,
        help='Image height, default is 800. When mode is set to "music", '
             'image height will be ignored and set to same as width.'
    )
    parser.add_argument(
        '--column',
        type=int,
        default=7,
        help='Number of columns in the image gird, default is 7.'
    )
    parser.add_argument(
        '--user_agent',
        type=str,
        default='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 '
                'Safari/537.36',
        help='User-Agent used in request, default is Chrome.'
    )
    parser.add_argument(
        '--cache_folder',
        type=str,
        default='cache',
        help='Cache folder, default is "cache".'
    )
    parser.add_argument(
        '--cookie',
        type=str,
        default='',
        help='Cookie used in request, default is empty. specify this if you encounter error.'
    )
    parser.add_argument(
        '--output_folder',
        type=str,
        default='output',
        help='Output folder, default is "output".'
    )

    parsed, unparsed = parser.parse_known_args()
    if len(unparsed) != 0:
        print('Unknown arguments:', ', '.join(unparsed))
    return parsed


def main(args):
    douban_id = args.id
    mode = args.mode
    width = args.width
    height = args.height
    column = args.column
    target_year = args.year
    user_agent = args.user_agent
    cache_folder = args.cache_folder
    cookie = args.cookie
    output_folder = args.output_folder

    mkdir_if_not_exists(cache_folder)
    mkdir_if_not_exists(output_folder)

    if target_year != 'all' and not str(target_year).isnumeric():
        logging.error('The parameter year is neither set to "all" nor set to a valid year')
        exit(1)

    # When mode is set to music, keep the height and width equal
    if mode == 'music':
        height = width

    image_urls = get_image_urls(douban_id, mode, target_year, user_agent, cookie)

    logging.info(
        f'You have {"watched" if mode == "movie" else ("listened to" if mode == "music" else "read")} {len(image_urls)} '
        f'{"movies" if mode == "movie" else ("songs" if mode == "music" else "books")} '
        f'in {"all years" if target_year == "all" else target_year}.'
    )

    if len(image_urls) == 0:
        logging.info('Nothing to do, exit.')
        exit(0)

    logging.info('Start downloading images...')
    image_paths = download_images(image_urls, cache_folder, mode)
    logging.info('Download finished.')
    output_filename = generate_output_filename(douban_id, mode)
    output_path = os.path.join(output_folder, output_filename)
    logging.info(f'Generating image grid to {output_path}...')
    generate_image_grid(image_paths, column, height, width, output_path)
    logging.info('Finished.')
    logging.info(f'Image grid generated at {output_path}.')


if __name__ == '__main__':
    init_logging()
    main(parse_args())
