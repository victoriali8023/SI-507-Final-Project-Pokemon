from bs4 import BeautifulSoup
import requests
import json
import sqlite3
from flask import Flask, render_template,request
import plotly
import plotly.graph_objects as go
import pandas as pd

app = Flask(__name__)

baseurl = 'https://pokeapi.co/api/v2/'

CACHE_FILENAME = "cache.json"



def load_cache():
    ''' Opens the cache file if it exists and loads the JSON into
    the CACHE_DICT dictionary.
    if the cache file doesn't exist, creates a new cache dictionary
    
    Parameters
    ----------
    None
    
    Returns
    -------
    The opened cache: dict
    '''

    try:
        cache_file = open(CACHE_FILENAME, 'r')
        cache_file_contents = cache_file.read()
        cache = json.loads(cache_file_contents)
        cache_file.close()
    except:
        cache = {}
    return cache


cache = load_cache()


def save_cache(cache):
    ''' Saves the current state of the cache to disk
    
    Parameters
    ----------
    cache: dict
        The dictionary to save
    
    Returns
    -------
    None
    '''
    cache_file = open(CACHE_FILENAME,'w')
    contents_to_write = json.dumps(cache)
    cache_file.write(contents_to_write)
    cache_file.close()


def make_url_request_using_cache(url, cache):
    '''Check the cache for a saved result for this baseurl+params:values
    combo. If the result is found, return it. Otherwise send a new 
    request, save it, then return it.
    
    Parameters
    ----------
    url: string
        The unique key to retrieve the value
    cache: dict
        A dictionary of cache to check whether the data is in the cache
    
    Returns
    -------
    dict
        the results of the query as a dictionary loaded from cache
    '''

    if (url in cache.keys()):
        print("Using cache")
        return cache[url]  
    else:
        print("Fetching")
        response = requests.get(url) 
        cache[url] = response.text 
        save_cache(cache)       
        return cache[url]


def get_explore_pokemon_web_url():
    '''
    Make a dictionary that maps pokedex to pokemons' page url
    '''
    url = 'https://www.pokemon.com/us'
    
    response = make_url_request_using_cache(url, cache)
    soup = BeautifulSoup(response, 'html.parser')
    
    searching_div = soup.find(class_='container')
    searching_section = searching_div.find(id = 'pokemon-character-slider')
    searching_small_div = searching_section.find(class_='slider-more-button')
    searching_small_div2 = searching_small_div.find(class_='column-12 push-1')
    searching_small_div3 = searching_small_div2.find(class_='content-block content-block-full')
    searching_a = searching_small_div3.find('a', class_='button button-black right')
 
    explore_link = url + searching_a['href'].replace('us/', '')

    return explore_link


def get_pokemon_profile(new_link):
    '''
    get name, image source, category, abilityId, height, weight, type1, type2 from provided website
    example: new_link = 'https://www.pokemon.com/us/pokedex/ivysaur'
             could use poke_name or pokedex to search
    '''
    new_response = make_url_request_using_cache(new_link, cache)
    new_soup = BeautifulSoup(new_response, 'html.parser')

    row_to_store = [] #take care of shallow copy and replace!


    searching_section = new_soup.find(class_='section pokedex-pokemon-details')
    searching_image = searching_section.find('img')
    poke_img = searching_image['src']
    poke_name = searching_image['alt']

    searching_div = searching_section.find(class_='column-7 push-7')
    searching_ul1 = searching_div.find('ul')
    searching_lis2 = searching_ul1.find_all('li')

    category = searching_lis2[0].find('span',class_='attribute-value').text
    
    searching_a = searching_lis2[1].find('a',class_='moreInfo')
    ability_name = searching_a.find('span', class_='attribute-value').text
    ability_id = get_corresponding_effect_id(ability_name)

    row_to_store.append(poke_name)
    row_to_store.append(poke_img)
    row_to_store.append(category)
    row_to_store.append(ability_id)

    searching_info_div = new_soup.find(class_='info match-height-tablet')
    searching_ul = searching_info_div.find('ul')
    searching_lis1 = searching_ul.find_all('li')

    for li in searching_lis1:
        if  li.find(class_='attribute-title').text != 'Gender':
            value = li.find(class_='attribute-value').text
            row_to_store.append(value)

    searching_types = searching_section.find(class_='dtm-type')
    searching_ul = searching_types.find('ul')
    searching_lis2 = searching_ul.find_all('li')

    for li in searching_lis2:
        temp = li.find('a').text
        row_to_store.append(temp)

    return row_to_store


def get_corresponding_effect_id(ability_name):
    conn = sqlite3.connect('pokeInfo.sqlite')
    cur = conn.cursor()
    if ' ' in ability_name:
        ability_name = ability_name.replace(' ', '-')
    ability_name = ability_name.lower()


    q = f'''
        SELECT Id
        FROM Effects
        WHERE AbilityName = '{ability_name}'
    '''
    result = cur.execute(q).fetchone()
    conn.close()
    return result[0]
    
def get_ability_effect(effect_link):
    results = requests.get(effect_link).json()

    effect_1 = results['effect_changes']
    effect_2 = results['effect_entries']
    if len(effect_2) > 0:
        effect = effect_2[0]['effect']
        return effect
    elif len(effect_1) > 0:
        effect = effect_1[0]['effect_entries'][0]['effect']
        return effect
    else:
        return "No effect"


def get_ability_name(effect_link):
    results = requests.get(effect_link).json()
    name = results['name']

    return name

def get_chinese_name(effect_link):
    results = requests.get(effect_link).json()
    name = results['names'][0]['name']

    return name

def get_japanese_name(effect_link):
    results = requests.get(effect_link).json()
    name = results['names'][1]['name']

    return name

def create_effect_table():
    conn = sqlite3.connect("pokeInfo.sqlite")
    cur = conn.cursor()

    create_effects = '''
        CREATE TABLE IF NOT EXISTS "Effects" (
            "Id"    INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
            "AbilityName" TEXT NOT NULL,
            "Effect"  TEXT NOT NULL,
            "ChineseName" TEXT NOT NULL,
            "JapaneseName" TEXT NOT NULL
        );
    '''
    cur.execute(create_effects)

    conn.commit()
    conn.close()

def insert_row_to_effects(value):

    conn = sqlite3.connect('pokeInfo.sqlite')
    cur = conn.cursor()

    insert_effects = '''
        INSERT INTO Effects
        VALUES (NULL, ?, ?, ?, ?)
    '''
    cur.execute(insert_effects, value)
    conn.commit()
    conn.close()

def create_pokemon_table():
    conn = sqlite3.connect("pokeInfo.sqlite")
    cur = conn.cursor()

    create_pokemon = '''
        CREATE TABLE IF NOT EXISTS 'Pokemon' (
            'Id'    INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
            'Name'  TEXT NOT NULL,
            'ImageSource' TEXT NOT NULL,
            'Category' TEXT NOT NULL,
            'AbilityID' INTEGER NOT NULL,
            'Height' TEXT NOT NULL,
            'Weight' TEXT NOT NULL,
            'Type1' TEXT NOT NULL,
            'Type2' TEXT,
            FOREIGN KEY(AbilityID) REFERENCES Effects(ID)
        );
    '''
    cur.execute(create_pokemon)

    conn.commit()
    conn.close()

def insert_row_to_pokemon(row):

    conn = sqlite3.connect('pokeInfo.sqlite')
    cur = conn.cursor()
    
    insert_pokemon = '''
        INSERT INTO Pokemon
        VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    cur.execute(insert_pokemon, row)
    conn.commit()
    conn.close()

def find_pokemon_in_db(like_type, like_number, translation):
    conn = sqlite3.connect('pokeInfo.sqlite')
    cur = conn.cursor()

    q = f'''
        SELECT Name, ImageSource, Category, {translation}, Effect, Height, Weight, Type1, Type2
        FROM Pokemon
            JOIN Effects
              ON Pokemon.AbilityID=Effects.Id
        WHERE Effects.Id = {like_number} OR Type1 = '{like_type}' OR Type2 = '{like_type}'
        LIMIT 1
    '''
    result = cur.execute(q).fetchone()
    conn.close()
    return result


def get_ability_raraity(ability_name):
    conn = sqlite3.connect('pokeInfo.sqlite')
    cur = conn.cursor()

    q = f'''
        SELECT Count(Name)
        FROM Pokemon
            JOIN Effects
              ON Pokemon.AbilityID=Effects.Id
        WHERE AbilityName = '{ability_name}'
    '''
    ability_count = cur.execute(q).fetchone()
    labels = [ability_name, 'Other abilities']
    values = [ability_count[0], 500 - ability_count[0]]
    conn.close()

    df = pd.DataFrame({'x': labels, 'y': values}) # creating a sample dataframe
    data = [
        go.Pie(
            labels=df['x'], # assign x as the dataframe column 'x'
            values=df['y'],
            pull=[0.2, 0]
        )
    ]

    graphJSON = json.dumps(data, cls=plotly.utils.PlotlyJSONEncoder)

    return graphJSON


def get_all_ability_names():
    conn = sqlite3.connect('pokeInfo.sqlite')
    cur = conn.cursor()

    q = f'''
        SELECT AbilityName
        FROM Effects
    '''
    ability_name_row = cur.execute(q).fetchall()
    ability_name_list = []
    for i in range(0, 234):
        ability_name_list.append(ability_name_row[i][0])
        
    conn.close()
    return ability_name_list


def get_count(where):
    conn = sqlite3.connect('pokeInfo.sqlite')
    cur = conn.cursor()

    q = f'''
        SELECT Count(Name)
        FROM Pokemon
            JOIN Effects
              ON Pokemon.AbilityID=Effects.Id
        WHERE {where}
    '''
    ability_count_row = cur.execute(q).fetchone()
    ability_count = ability_count_row[0]
    conn.close()

    return ability_count



@app.route('/sizes')
def size_distribution():
    
    xs_where = "Weight BETWEEN '0 lbs' AND '20 lbs'"
    xs_size = get_count(xs_where)

    s_where = "Weight BETWEEN '21 lbs' AND '40 lbs'"
    s_size = get_count(s_where)

    m_where = "Weight BETWEEN '41 lbs' AND '60 lbs'"
    m_size = get_count(m_where)

    l_where = "Weight BETWEEN '61 lbs' AND '80 lbs'"
    l_size = get_count(l_where)

    xl_where = "Weight BETWEEN '81 lbs' AND '100 lbs'"
    xl_size = get_count(xl_where)
    
    xvals = ['Extra small', 'Small', 'Medium', 'Large', 'Extra Large']
    yvals = [xs_size, s_size, m_size, l_size, xl_size]

    bar_data = go.Bar(x=xvals, y=yvals)
    basic_layout = go.Layout(title="Size Bar Graph")
    
    fig = go.Figure(data=bar_data, layout=basic_layout)
    fig.show()

    return render_template('index.html')


@app.route('/ability')
def abiility_distribution():
    name_list = get_all_ability_names()
    count_list = []
    for name in name_list:
        where = 'AbilityName = ' + "'" + name + "'"
        count = get_count(where)
        count_list.append(count)
    
    labels = name_list
    values = count_list

    fig = go.Figure(data=[go.Pie(labels=labels, values=values)])
    fig.show()

    return render_template('index.html')


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/profile', methods=['POST'])
def profile():
    user_name = request.form['name']
    # like_size = request.form['sizes']
    like_number = request.form['index']
    like_type = request.form['type']
    translation = request.form['translation']

    info = find_pokemon_in_db(like_type,like_number, translation)

    return render_template('profile.html', 
                            user_name=user_name,
                            poke_name=info[0],
                            image=info[1], 
                            category=info[2],
                            ability=info[3],
                            effect=info[4],
                            height=info[5],
                            weight=info[6],
                            type1=info[7],
                            type2=info[8]
                            )

@app.route('/rarity')
def rarity():
    ability = request.args.get('my_var', None)

    pie = get_ability_raraity(ability_name=ability)
    return render_template('rarity.html', plot=pie)


if __name__ == '__main__':
    create_effect_table() 
    create_pokemon_table()
    explore_link = get_explore_pokemon_web_url()
    for i in range(1, 234):
        effect_link = baseurl + 'ability/' + str(i) +'/'
        effect = get_ability_effect(effect_link)
        name = get_ability_name(effect_link)
        chinese = get_chinese_name(effect_link)
        japanese = get_japanese_name(effect_link)
        value = [name, effect, chinese, japanese]
        insert_row_to_effects(value)

    for i in range(1, 501):
        poke_link = explore_link + str(i) + '/'
        row = get_pokemon_profile(poke_link)
        if len(row) == 7:
            row.append(None)
        insert_row_to_pokemon(row)

    #app.run(debug=True)
    app.run(debug=False)
    





 












 
   