import os
import requests
import json
import time
import logging

from dotenv import load_dotenv
from tqdm import tqdm


class Vkontakte:
    HEAD_URL_VK = 'https://api.vk.com/method'

    def __init__(self, owner_id, album_id='wall', number_photos=5):
        self.owner_id = owner_id
        self.album_id = album_id
        self.number_photos = number_photos
        self.access_token = os.getenv('ACCESS_TOKEN_VK')

    def get_photo(self):
        params = {
            'access_token': self.access_token,
            'v': '5.154',
            'owner_id': self.owner_id,
            'album_id': self.album_id,
            'extended': 1,
            'photo_sizes': 1
        }
        try:
            print('Собираем фото в Vkontakte.')
            response = requests.get(f'{self.HEAD_URL_VK}/photos.get', params=params)

            response.raise_for_status()

            res = response.json()

            if 'error' in res:
                error_code = res['error']['error_code']
                error_msg = res['error']['error_msg']

                raise Exception(
                    logging.error(f'Ошибка формирования списка файлов с VK. Код ошибки: {error_code} - {error_msg}')
                )

            else:

                logging.info(f'Сформирован список фото для загрузки')

                return response.json()['response']['items'][:self.number_photos]

        except Exception:
            return []


class YandexDisk:
    HEAD_URL_YD = 'https://cloud-api.yandex.net/v1/disk/resources'

    def __init__(self, owner_id, access_token_yd, file_list):
        self.owner_id = owner_id
        self.access_token_yd = access_token_yd
        self.file_list = file_list
        self.headers_yd = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'OAuth {self.access_token_yd}'
        }

    def session(self):
        session = requests.Session()
        session.headers.update(self.headers_yd)

        return session

    def create_folder(self, session):
        params = {
            'path': self.owner_id,
            'fields': 'public_key'
        }
        try:
            print('Создаем папку на YandexDisk.')
            response = session.get(self.HEAD_URL_YD, params=params)
            response.raise_for_status()
            
            if response.ok:
                if response.json().get('public_key'):
                    response = session.put(f'{self.HEAD_URL_YD}/unpublish', params=params)
                    response.raise_for_status()
                    time.sleep(2)
                    
                params.update({
                    'fields': 'name',
                    'permanently': 'true'
                    })
                
                get_response = session.get(self.HEAD_URL_YD, params=params)
                while get_response.ok:
                    session.delete(self.HEAD_URL_YD, params=params)
                    get_response = session.get(self.HEAD_URL_YD, params=params)
                response.raise_for_status()
                
            time.sleep(2)
            del params['permanently']
            response = session.put(self.HEAD_URL_YD, params=params)

            response.raise_for_status()
            
            time.sleep(2)
            response = session.put(f'{self.HEAD_URL_YD}/publish', params=params)

            params.update({'fields':'public_url'})
            
            response = session.get(self.HEAD_URL_YD, params=params)
            response.raise_for_status()
            
            res = response.json()
            logging.info('Создана папка на YandexDisk.')

        except Exception as e:
            logging.error(f'Ошибка создания папки на YandexDisk. {e}')
        
        return res['public_url']

    def loader(self, file_name, file_url, session):
        params = {
            'path': f'/{self.owner_id}/{file_name}',
            'url': file_url,
        }
        try:
            time.sleep(2)
            response = session.post(f'{self.HEAD_URL_YD}/upload', params=params)

            response.raise_for_status()
        except Exception as e:
            logging.error(f'Ошибка загрузки файла на YandexDisk. {e}')

    def upload_photo(self):
        session = self.session()

        try:
            if self.file_list == []:
                raise

            json_file_list = []

            public_url = self.create_folder(session)

            for items in tqdm(self.file_list, bar_format="{l_bar}{bar:30}| {n_fmt}/{total_fmt}",
                              desc="Загружаем фото", colour='green'):
                file_url = items['sizes'][-1]['url']
                file_type = file_url.split("?")[0][-3:]
                file_name = f'{items["likes"]["count"]}.{file_type}'
                file_size = f'{items["sizes"][-1]["height"]}x{items["sizes"][-1]["width"]}'

                if file_name in [x['file_name'] for x in json_file_list]:
                    file_name = f'{items["date"]}-{file_name}'

                self.loader(file_name, file_url, session)

                json_file_list.append({
                    "file_name": file_name,
                    "size": file_size
                })

            logging.info(f'Файлы загружены на YandexDisk. {public_url}')

            with open('upload_photo_list.json', 'w', encoding='utf-8') as f:
                json.dump(json_file_list, f, ensure_ascii=False, indent=4)

            logging.info('Список загруженных файлов в формате json сформирован (upload_photo_list.json).')
            print('Фотографии успешно загружены!', f'Ссылка для просмотра: {public_url}', sep='\n')

            return json_file_list
        except Exception:
            print('Ошибка при загрузке фотографий. Более подробно в log-файле')


if __name__ == '__main__':
    load_dotenv()

    logging.basicConfig(level=logging.INFO, filename="backup_log.log", filemode="w", encoding='utf-8',
                        format="%(asctime)s %(levelname)s %(message)s")

    # Введите ID пользователя Vkontakte
    owner_id = 353555

    # Введите токен с Полигона Яндекс.Диска
    access_token_yd = os.getenv('ACCESS_TOKEN_YD')

    # Введите идентификатор альбома для скачивания ('profile', 'wall', 'saved')
    album_id = 'profile'

    # Введите количество фото которые хотите сохранить (по умолчанию = 5)
    number_photos = 5

    vk = Vkontakte(owner_id, album_id=album_id, number_photos=number_photos)
    yd = YandexDisk(owner_id, access_token_yd, vk.get_photo())
    yd.upload_photo()
